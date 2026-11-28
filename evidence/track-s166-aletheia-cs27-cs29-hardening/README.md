# Track S166: CS-27..CS-29 Portal Interposition, Thin-Coordinator Crossover, & EXP-Q46b Lean-Audit Hardening

Standalone, file-disjoint extension bundle providing:

1. **CS-27 (`SOP-18`) — `aletheia/portfolio_dag.py`** (backed by shared strict Zone-B helper `aletheia/_strict_zone_b.py`):
   - Cycle-safe iterative 3-color DFS validator for recursive nested-link portal graphs (`depth == 0` root reachability, non-decreasing edge depths, zero anti-bot bypass, `SHALLOW_PORTAL_BLINDNESS` guard, uniform support for `from/to`, `source/target`, and `src/dst` edge keys plus `depth`/`min_depth` node fields).
   - Symmetric exact-rational GitHub (`is_private == false`, branch/PR enumeration) and Hugging Face (`models`/`datasets`/`spaces`/`collections`, explicit `zero_hf_disambiguation_query`) coverage validator.
2. **CS-28 (`SOP-19`) — `aletheia/portal_interpose.py`**:
   - Standalone Turn-0 domain-stripped multi-pillar interposition engine across 7 orthogonal pillars with zero hardcoded host paths, optional read-only SQLite archive querying (`?mode=ro` + `PRAGMA query_only = ON`, WAL/SHM safe), fail-closed Law-5 operator/obstruction guard, and regression fixtures proving zero-keyword cross-pillar discovery (Hadwiger 3D -> Optimization/Quantization; PFC Loopy BP/Carving -> Connectome).
3. **CS-29 (`SOP-20`) — `aletheia/thin_coordinator.py` + `ThinCoordInterpose.lean`**:
   - Exact pure-rational (`fractions.Fraction`) Thin-Coordinator vs. Inline-Tool Context-Tax Crossover Theorem ($T \cdot B \cdot c_{\mathrm{hit}} > W_{\mathrm{worker}} + T \cdot s \cdot c_{\mathrm{hit}} \iff T \cdot (B - s) \cdot c_{\mathrm{hit}} > W_{\mathrm{worker}}$) with compaction-frequency ($dk \cdot K_{\mathrm{comp}}$) and cold-miss reactivation ($m_{\mathrm{cold}} \cdot (B - s) \cdot c_{\mathrm{miss}}$) amplification.
   - 12 pure-`Init` Lean `4.36.0` theorems (`0` `sorry`/`axiom`/`Classical.choice`).
   - Deterministic JSONL transcript bloat analyzer supporting multiple session log schemas without leaking private host paths or raw text.
4. **EXP-Q46b — `aletheia/lean_audit_hardening.py`**:
   - Hardened Lean 4.36.0 source, project (`lakefile.toml` vs. `lake-manifest.json`, `lakefile.lean`, nonexistent/empty target dirs), Comparator `config.json` (`enable_nanoda: false`, solution-imports-challenge), and `TargetAudit` (`loadExts := false`, serialized `constNames`, `sorryAx` / `ofReduceBool` / `trustCompiler` / `partial`) bypass audit suite.

## Quick Verification

```bash
cd evidence/track-s166-aletheia-cs27-cs29-hardening
python3 -I -B test_s166_cs27_cs29_r5.py
python3 -I -O -B test_s166_cs27_cs29_r5.py
python3 -I -B -W error test_s166_cs27_cs29_r5.py
python3 -I -B s166_cs27_cs29_audit.py --check s166_cs27_cs29_certificate.json
python3 -I -B s166_cs27_cs29_audit.py --check s166_cs27_cs29_certificate.json --live-lean
```
