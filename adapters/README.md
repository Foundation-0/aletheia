# Platform Adapters — Drop-In Aletheia Everywhere

**The Aletheia Method** ships with first-class, zero-dependency adapters for every major AI coding and research environment. All six adapters share the exact same **5 Operational Laws**, **9 Verification Gates**, **R1–R5 Gate Contracts**, and **Novelty/Oracle Taxonomy** defined in [`../spec/LAWS_AND_GATES.md`](../spec/LAWS_AND_GATES.md).

## Platform Comparison & 1-Line Install

| Platform | Adapter Directory | Mechanism | 1-Line Automated Install (`aletheia` CLI) | Manual Copy Target |
|---|---|---|---|---|
| **Antigravity (AGY)** | [`antigravity/`](antigravity/README.md) & [`.agents/plugins/aletheia-research/`](../.agents/plugins/aletheia-research/plugin.json) | Native plugin (global rule + skill + references) | `python3 -m aletheia install --target antigravity` | `~/.gemini/config/plugins/aletheia-research/` (global) or `<repo>/.agents/plugins/aletheia-research/` |
| **Claude Code** | [`claude-code/`](claude-code/README.md) | `CLAUDE.md` + plugin manifest + `/aletheia` command + subagent specs | `python3 -m aletheia install --target claude-code --dest <repo>` | `<repo>/CLAUDE.md` + `<repo>/.claude/` |
| **OpenAI Codex / AGENTS.md** | [`codex/`](codex/README.md) | Universal `AGENTS.md` rule file | `python3 -m aletheia install --target codex --dest <repo>` | `<repo>/AGENTS.md` |
| **Cursor** | [`cursor/`](cursor/README.md) | `.cursor/rules/aletheia-research.mdc` (always-apply MDC rule) | `python3 -m aletheia install --target cursor --dest <repo>` | `<repo>/.cursor/rules/aletheia-research.mdc` |
| **Gemini CLI** | [`gemini-cli/`](gemini-cli/README.md) | `GEMINI.md` workspace or global context file | `cp adapters/gemini-cli/GEMINI.md <repo>/GEMINI.md` | `<repo>/GEMINI.md` or `~/.gemini/GEMINI.md` |
| **Any Generic LLM / Web / API** | [`generic-llm/`](generic-llm/SYSTEM_PROMPT.md) | Portable system prompt + 4-phase single-agent runbook | Paste [`generic-llm/SYSTEM_PROMPT.md`](generic-llm/SYSTEM_PROMPT.md) | System prompt / Custom Instructions |

> **Tip:** Preview any installation safely without writing files by adding `--dry-run` to `python3 -m aletheia install --target <platform> --dry-run`.

## Choosing Multi-Agent vs. Single-Agent Mode

- **Multi-agent runtimes** (Antigravity swarms, Claude Code subagents, multi-session orchestrators): Pair your platform adapter with the modular role briefs in [`../prompts/`](../prompts/coordinator.md) (`coordinator`, `portal-keeper`, `domain-probe`, `synthesizer`, `verifier-tomography`, `peer-weaver`).
- **Single-agent sessions** (Codex, Cursor, Gemini CLI, API/chat): Follow [`generic-llm/SINGLE_AGENT_LOOP.md`](generic-llm/SINGLE_AGENT_LOOP.md) or [`../prompts/single-agent-loop.md`](../prompts/single-agent-loop.md) to enforce strict phase separation (**Portal $\to$ Probe $\to$ Tomography $\to$ Resonance**).

## Verifying Your Installed Setup

After installing an adapter into any research repository, initialize the expedition workspace and run the self-check:

```bash
python3 -m aletheia init . --domain mathematics
python3 -m aletheia audit-check .
```
