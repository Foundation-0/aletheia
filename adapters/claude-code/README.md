# Claude Code Adapter

This directory provides a complete, drop-in Claude Code setup for **The Aletheia Method**, including:

- [`CLAUDE.md`](CLAUDE.md) — Project-level operational rules (The 5 Laws, R1–R7, Novelty Bar)
- [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) — Claude Code plugin manifest
- [`commands/aletheia.md`](commands/aletheia.md) — `/aletheia` slash command launching the 4-phase Resonance Loop or multi-agent swarm
- [`agents/portal-keeper.md`](agents/portal-keeper.md) — Dedicated `portal-keeper` subagent definition (active throughout the session)
- [`agents/verifier-tomography.md`](agents/verifier-tomography.md) — Dedicated zero-shared-code adversarial `verifier-tomography` subagent definition

## Option 1 — Automated CLI Install (Recommended)

```bash
# Preview changes safely
python3 -m aletheia install --target claude-code --dest /path/to/your-repo --dry-run

# Install into your repository
python3 -m aletheia install --target claude-code --dest /path/to/your-repo
```

## Option 2 — Manual Install

```bash
TARGET=/path/to/your-repo
cp adapters/claude-code/CLAUDE.md "$TARGET/CLAUDE.md"
mkdir -p "$TARGET/.claude/commands" "$TARGET/.claude/agents"
cp adapters/claude-code/commands/aletheia.md "$TARGET/.claude/commands/aletheia.md"
cp adapters/claude-code/agents/*.md "$TARGET/.claude/agents/"
```

## Usage in Claude Code

1. Open Claude Code inside `$TARGET`. `CLAUDE.md` activates the 5 Laws automatically.
2. Run `/aletheia <research question or raw source path>` to launch an Aletheia cycle.
3. Delegate raw-source re-entry to the `portal-keeper` subagent and independent clean-room verification to the `verifier-tomography` subagent (never verifying inside the same context that wrote the proof/script!).
4. Run `python3 -m aletheia audit-check .` and `python3 -m aletheia diagnose .` before opening a Draft PR.
