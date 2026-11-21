# Prompt Template: Wave 2+ Multi-Machine Compute Handoff

Use this prompt when verified Wave 1 discoveries reach the compute, memory, GPU, or formal-toolchain ceiling of the current workstation and must be handed cleanly to a stronger machine or remote research swarm with **zero context loss**.

---

```markdown
You are packaging a **Wave 2+ Portable Compute Handoff** for **The Aletheia Method** so a stronger workstation, CPU cluster, formal-proof host, or GPU node can pick up verified frontiers immediately.

INPUTS (read-only):
- `<WORKSPACE>/verification/AUDIT_LOG.md` (every verified Wave 1 audit ID, SHA-256, and scope limit)
- `<WORKSPACE>/cartography/frontier_portals.md` & `<WORKSPACE>/peer-web/PEER_WEB.md`
- All live public repository URLs, Draft PR URLs, and starting commit SHAs

DELIVERABLES:
1. **`NEXT_WAVES_COMPUTE.md`** — Human- and agent-readable execution specification grouped by compute wave (`Wave 2A`, `Wave 2B`, ...).
2. **`next_waves_manifest.json`** — Machine-readable manifest strictly conforming to `schemas/compute_handoff.v1.schema.json` (`schema: "aletheia.compute_handoff.v1"`), validated cleanly via:
   `python3 -m aletheia handoff next_waves_manifest.json`

MANDATORY FIELDS FOR EVERY WAVE 2+ TASK:
- **Task ID & Title**
- **Compute Tier** (`tier_1_cpu`, `tier_2_formal_heavy_exact`, `tier_3_gpu_checkpoints`, or explicit hardware/VRAM/RAM/toolchain spec)
- **Target Repos, Open Draft PRs, Exact Starting Commit SHAs, and Exact File Paths** (verified live—zero guessed filenames!)
- **Wave 1 Verified Baseline** (exact `AUDIT-NNN` IDs, `N2`/`N1` tags, and honest scope boundaries—e.g. local vs. global, `uncompiled_source`, ensemble-vs-single-shot)
- **Exact Bootstrap & Baseline Verification Command** (cloning + `gh pr checkout` + running the pinned Wave 1 script under `python3 -I -O -B -W error` so the new machine verifies Wave 1 before starting Wave 2)
- **Sharp Mathematical / Physical / Empirical Hypothesis** (plus algorithmic guidance where naive brute force scales exponentially!)
- **Oracle Class (`exact` / `sampled` / `anchor`) & Explicit Falsification Gate** (exact numerical/algebraic condition that kills the hypothesis, plus mandatory negative controls)

HYGIENE & PORTABILITY GATES (MANDATORY):
- `0` personal/local machine paths (no home-directory paths, no `file://` URIs)
- `0` secrets or tokens
- `0` CRLF line endings
- Valid JSON passing `python3 -m aletheia handoff <manifest.json>` and `python3 -m aletheia audit-check .`
```
