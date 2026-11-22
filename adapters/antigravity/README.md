# Antigravity (AGY) Adapter

Antigravity natively discovers the Aletheia plugin bundle at [`.agents/plugins/aletheia-research/`](../../.agents/plugins/aletheia-research/plugin.json), providing:

- **Always-active global/workspace rule:** `rules/AGENTS.md` (The 5 Operational Laws)
- **Discoverable research skill:** `skills/aletheia-research/SKILL.md` (Swarm architecture, 4-phase single-agent loop, CLI commands, anti-pattern guards)
- **Compact reference sheet:** `skills/aletheia-research/references/QUICK_REFERENCE.md`

## Option 1 — Automated CLI Install (Recommended)

```bash
# Preview first
python3 -m aletheia install --target antigravity --dry-run

# Install globally into ~/.gemini/config/plugins/aletheia-research/
python3 -m aletheia install --target antigravity
```

## Option 2 — Workspace-Scoped Install (Per Repository)

Copy the `.agents/plugins/aletheia-research/` folder into any target repository so every contributor or remote machine cloning that repo inherits Aletheia automatically:

```bash
mkdir -p /path/to/target-repo/.agents/plugins
cp -r .agents/plugins/aletheia-research /path/to/target-repo/.agents/plugins/
```

## Option 3 — Global Manual Install (All Projects on This Machine)

```bash
mkdir -p ~/.gemini/config/plugins
cp -r .agents/plugins/aletheia-research ~/.gemini/config/plugins/aletheia-research
```

To enable globally, ensure `"aletheia-research"` is listed as enabled in `~/.gemini/config/settings.json` (if your Antigravity profile uses an explicit plugin allowlist).

## Swarm Role Templates for Antigravity

When spawning an Antigravity swarm (`swarm{action:"add", ...}`), pair this plugin with the modular briefs in [`../../prompts/`](../../prompts/coordinator.md):
- `portal-keeper` ([`../../prompts/portal-keeper.md`](../../prompts/portal-keeper.md)) — stays active across all rounds
- `<domain>-probe` ([`../../prompts/domain-probe.md`](../../prompts/domain-probe.md)) — real upstream tests, zero proxy substitution
- `synthesizer` ([`../../prompts/synthesizer.md`](../../prompts/synthesizer.md)) — exact cross-domain operator bridges
- `verifier` ([`../../prompts/verifier-tomography.md`](../../prompts/verifier-tomography.md)) — zero-shared-code adversarial tomography
- `peer-weaver` ([`../../prompts/peer-weaver.md`](../../prompts/peer-weaver.md)) — live peer PR mapping & Wave 2+ handoff
