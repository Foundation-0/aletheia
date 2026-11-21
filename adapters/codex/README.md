# OpenAI Codex / `AGENTS.md` Adapter

OpenAI Codex (and any `AGENTS.md`-compatible coding agent) automatically loads `AGENTS.md` from the repository root.

## Option 1 — Automated CLI Install (Recommended)

```bash
# Preview safely
python3 -m aletheia install --target codex --dest /path/to/your-repo --dry-run

# Install AGENTS.md into your repository root
python3 -m aletheia install --target codex --dest /path/to/your-repo
```

## Option 2 — Manual Install

```bash
cp adapters/codex/AGENTS.md /path/to/your-repo/AGENTS.md
```

## Workflow in Codex

1. Initialize workspace scaffolding: `python3 -m aletheia init . --domain <your-domain>`.
2. Run the 4-phase single-agent loop ([`../../prompts/single-agent-loop.md`](../../prompts/single-agent-loop.md)) or spawn separate Codex tasks per role using [`../../prompts/`](../../prompts/coordinator.md).
3. Enforce clean-room verification by running `verification/checks/check_NNN_*.py` and `python3 -m aletheia audit-check .` before creating any Draft PR.
