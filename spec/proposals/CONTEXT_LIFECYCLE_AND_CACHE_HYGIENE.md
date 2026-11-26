# Proposal: Context Lifecycle & Cold-Cache Hygiene (`CS-26`)

## 1. Anti-Pattern `CS-26` — Context-Bloat & Cold-Cache Reactivation Trap

A worker thread accumulates history until its context is large, is left idle
past the prompt-cache lifetime, and is then reactivated. The reactivation pays
for the entire stale history again as an uncached cache miss, even though the
useful state could already live on disk and a fresh worker could start from
the small disk artifacts instead. The same failure mode appears as long
payloads pasted into chats and swarm boards, and as operational roles that
survive many waves by repeated compaction instead of rotating.

## 2. The Four Invariants

1. **Ephemeral worker retire & respawn.** Once a worker has landed its task
   cleanly on disk, has no active background work, and its history is no
   longer relevant to the next task, retire it permanently and spawn a fresh
   zero-context worker that references the exact disk artifacts.
2. **Cold-cache reactivation guard.** Never leave a bloated worker (default
   threshold: more than `150000` context tokens) parked idle past the
   prompt-cache TTL (default `300` seconds) only to reactivate it cold.
   Either retire it in favour of a fresh worker on the next round, or compact
   it manually before the idle gap (`/compact` in interactive sessions).
3. **External-file-in-place discipline.** Never pull long blocks of text, raw
   logs, multi-file digest manifests, full diffs, or large JSON payloads into
   chat sessions or swarm board messages. Write and read them in place on
   disk (for example under `verification/reports/` or `scratch/`), filter
   command output down to summaries, and keep board messages concise
   (`<= 12` lines: verdict or status, disk path, digest, next action).
4. **Wave-boundary rotation.** Rotate high-churn operational roles
   (cartographer/portal-keeper, verifier/router, peer-weaver, corpus
   compiler) between waves instead of accumulating recursive compactions
   inside a single thread. The disk artifacts, not the thread, carry state
   across the boundary.

## 3. Exact Pure-`Q` Billing Dominance Model

Let `L` be the parked worker's context size in tokens, `L_0` the fresh
worker's starting context, `L_sys` the fixed system/tool prefix, `S` the
compaction summary size, `tau_idle` the idle duration, and `tau_TTL` the
cache lifetime. Per-token prices are exact rationals: `c_miss` (uncached
input), `c_hit` (cached input), and `c_out` (output).

- Cold-cache reactivation cost: $C_{\text{cold}}(L) = c_{\text{miss}} L$ (when $\tau_{\text{idle}} \ge \tau_{\text{TTL}}$) vs. warm reactivation $C_{\text{warm}}(L) = c_{\text{hit}} L$.
- Fresh ephemeral respawn cost: $C_{\text{respawn}}(L_0) = c_{\text{miss}} L_0$ (strictly dominates cold reactivation whenever $L_0 < L$).
- Pre-idle compaction cost: $C_{\text{compact}}(L, L_{\text{sys}}, S) = c_{\text{hit}} L + c_{\text{out}} S + c_{\text{miss}}(L_{\text{sys}} + S)$. The $c_{\text{hit}} L$ term is the cached read of the full parked context that producing the summary requires while the worker is still warm, before it idles. Compaction strictly dominates cold reactivation whenever $L > L^* = (c_{\text{out}} S + c_{\text{miss}}(L_{\text{sys}} + S)) / (c_{\text{miss}} - c_{\text{hit}})$, which is defined only when $c_{\text{miss}} > c_{\text{hit}}$.

At the crossover `L = L*` compaction and cold reactivation cost exactly the
same, so compaction does not strictly dominate; at `L_0 = L` respawn and cold
reactivation cost exactly the same, so respawn does not strictly dominate.
When $c_{\text{miss}} \le c_{\text{hit}}$ the crossover is undefined
(`crossover_tokens` is `null`): the cached summarization read costs at least
as much per token as the cold re-read it would replace, so compaction never
strictly beats cold reactivation at any `L`.
The executable engine (`aletheia.context_hygiene.evaluate_reactivation_policy`)
compares these costs in exact rational arithmetic and returns
`RETIRE_AND_RESPAWN`, `PRE_IDLE_COMPACT`, or `KEEP_WARM` with exact rational
savings and the exact crossover threshold `L*`.

## 4. Executable Enforcement

- `python3 -m aletheia context-hygiene --self-test --json` — pure-`Q`
  policy self-test with fail-closed negative controls.
- `python3 -m aletheia context-hygiene --demo --json` — the three policies on
  fixed example inputs.
- `python3 -m aletheia context-hygiene --board <board.jsonl> --workers <workers.json> --json`
  — deterministic `CS-26` scan returning `aletheia.context_hygiene.v1` with
  status `CLEAN`, `WARNING`, or `ALERT`. Threshold flags:
  `--max-board-lines`, `--max-board-chars`, `--cold-context-tokens`,
  `--cache-ttl-seconds`, `--max-compactions`, and `--fail-on-warning`.

The workers payload is `{"workers": [{"id": "...", "context_tokens": 0, "idle_seconds": 0, "compactions": 0}]}`.
Board lines are strict JSON objects; a `text` field, when present, is the
measured message body. Inputs are read fail-closed: no symlinks (leaf or
ancestor), regular files only, a streaming `16 MiB` cap, strict UTF-8, and
float-free duplicate-free JSON with bounded integer size and nesting depth.

## 5. Scope

This proposal is harness-neutral operational guidance plus a deterministic
scanner. It measures only what the caller supplies (board lines and declared
worker counters) and prices policies only under the linear model above; it
does not observe any live session, cache, or bill.
