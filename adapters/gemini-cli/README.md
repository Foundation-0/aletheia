# Gemini CLI Adapter

Gemini CLI automatically loads `GEMINI.md` from the current repository root (or globally from `~/.gemini/GEMINI.md`).

## Workspace Install (Recommended)

```bash
cp adapters/gemini-cli/GEMINI.md /path/to/your-repo/GEMINI.md
```

## Global Install (All Projects)

```bash
mkdir -p ~/.gemini
cp adapters/gemini-cli/GEMINI.md ~/.gemini/GEMINI.md
```

*(If you already maintain a personal `~/.gemini/GEMINI.md`, append `adapters/gemini-cli/GEMINI.md` under a dedicated `## The Aletheia Method` section.)*

## Usage in Gemini CLI

1. Bootstrap your research workspace: `python3 -m aletheia init . --domain <your-domain>`.
2. Run each cycle using the 4-phase separation protocol ([`../../prompts/single-agent-loop.md`](../../prompts/single-agent-loop.md)).
3. Check runtime parity, hygiene, and anti-cave relapse diagnostics with `python3 -m aletheia audit-check .` and `python3 -m aletheia diagnose .`.
