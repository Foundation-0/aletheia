# Proposal: Portal Interposition (`CS-27`/`CS-28`), Thin-Coordinator Offload (`CS-29`), and Hardened Lean Audit (`EXP-Q46b`)

## 1. `CS-27` (`SOP-18`) — Recursive Nested-Link DAG & Symmetric GitHub+HF Coverage (`aletheia/portfolio_dag.py`, `aletheia/_strict_zone_b.py`)
- Reject cycles (`CYCLE_DETECTED`) via iterative 3-color DFS, enforce depth-0 root reachability (`UNREACHABLE_DEEP_NODE`), non-decreasing edge depths (`DEPTH_REGRESSION`), zero anti-bot bypass (`ANTIBOT_BYPASS_FORBIDDEN`), and fail closed on shallow depth-0-only crawls (`SHALLOW_PORTAL_BLINDNESS`).
- Supports Wave-22 node (`id`/`url`, `depth`/`min_depth`) and edge (`from`/`to`, `source`/`target`, `src`/`dst`) schemas uniformly, backed by shared fail-closed Zone-B OS-descriptor/strict-JSON checks (`aletheia/_strict_zone_b.py`).
- Require symmetric GitHub (`is_private == false`, `SOP-9` non-`main` branches + open PRs) and Hugging Face (`model`, `dataset`, `space`, `collection`, explicit `zero_hf_disambiguation_query` when empty) coverage in exact `fractions.Fraction` arithmetic.

## 2. `CS-28` (`SOP-19`) — Turn-0 Domain-Stripped Full-Portfolio Interposition (`aletheia/portal_interpose.py`)
- Strip disciplinary labels (`Stage A`) before scoring 7 orthogonal active portfolio pillars in exact `Fraction` ratios.
- Enforce fail-closed Law-5 guard (`enforce_law5_interpose_guard`): Turn-0 matches default to `CANDIDATE_NEEDS_PROOF` and cannot be promoted without either an explicit typed operator map (`EXACT_OPERATOR_TRANSFER`) or an explicit impossibility/obstruction witness (`STRUCTURAL_OBSTRUCTION`).
- Regressions prove zero-keyword cross-pillar detection for Hadwiger 3D -> Quantization and Loopy BP/Carving -> Connectome.

## 3. `CS-29` (`SOP-20`) — Thin-Coordinator Pure-Q Crossover Theorem & Transcript Bloat (`aletheia/thin_coordinator.py`, `ThinCoordInterpose.lean`)
- Exact pure-$\mathbb{Q}$ base crossover:
  $$T \cdot B \cdot c_{\mathrm{hit}} > W_{\mathrm{worker}} + T \cdot s \cdot c_{\mathrm{hit}} \iff T \cdot (B - s) \cdot c_{\mathrm{hit}} > W_{\mathrm{worker}}.$$
- Compaction-frequency (`dk * K_comp`) and cold-cache reactivation (`m_cold * (B - s) * c_miss`) amplification strictly lower the offload payload crossover and preserve monotonicity (proven in both pure-`Fraction` Python and 12 pure-`Init` `Lean 4.36.0` theorems with `0` `sorry`/`Classical.choice`).
- Deterministic JSONL transcript bloat analyzer measures `inline_tool_output_ratio_q` and `> 40`-line offload violations across session formats while emitting zero private host paths or raw text.

## 4. `EXP-Q46b` — Lean 4 Trust-Boundary Bypass Hardening (`aletheia/lean_audit_hardening.py`)
- Closes real-world bypasses documented in `arXiv:2611.32334v2` (`check_clean.py`) and `solved-conjectures#902` (`TargetAudit`): `sorryAx`, `ofReduceBool`, `trustCompiler`, `partial` on theorem-carrying definitions, `enable_nanoda: false`, nonexistent/empty target directories returning `RC=0`, `lakefile.lean` omission, literal/comment lexer escapes (`"/-"`), and `TargetAudit` `constNames` completeness / `loadExts := false` checks.

## 5. Verification Alignment (`R1`–`R7`, Ten Verification Gates)
All five modules (`aletheia/{_strict_zone_b,portfolio_dag,portal_interpose,thin_coordinator,lean_audit_hardening}.py`) are pure Python stdlib, float-free on exact gates, zero-bare-assert, and verified across all three isolated Python modes (`-I -B`, `-I -O -B`, `-I -B -W error`) and R5 single-site mutation testing (`100.0%` kill rate).
