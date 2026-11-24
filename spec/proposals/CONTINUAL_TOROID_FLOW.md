# Proposal: Continual Rotational-Transform Law ($\iota_W > 0$) & Swarm-Flow Diagnostics

**Status:** **Executable Additive Module Ready for Review** (`aletheia/flow_audit.py`, `tests/test_continual_toroid_flow_r5.py`; pure Python 3 standard library, exact $\mathbb{Z}/\mathbb{Q}$ arithmetic, zero floats, zero bare `assert`s, zero edits to existing core modules).

---

## 1. Motivation: The Asymptotic Blind Spot in Lifetime-Ratio `CS-01`

A healthy Aletheia discovery swarm maintains a continual coupled **toroidal–poloidal recursion**

$$\mathbf{B} = B_\phi \hat{\boldsymbol{\phi}} + B_\theta \hat{\boldsymbol{\theta}},$$

where toroidal execution ($B_\phi$: probes, proofs, verifiers, and implementation hardening) stays continuously wound by poloidal feedback ($B_\theta$: portal-keeping, cartography, cross-track weaving, and synthesis). When poloidal winding halts while toroidal traffic continues, the swarm collapses into isolated local hardening loops: discoveries stop folding back into `frontier_portals.md`, cross-track operator bridges go unnoticed, and locally verified tracks strand without synthesis or external shipment.

In existing `aletheia/diagnose.py`, `CS-01` (*Static-Map Trap*) evaluates a **lifetime-ratio** guard:

$$\mathrm{last\_seq} < \frac{7}{20}\,\mathrm{max\_seq} \qquad (\text{written as } \mathrm{last\_seq} < 0.35\,\mathrm{max\_seq}).$$

### Algebraic Proof of Asymptotic Blindness

Suppose a cartographer / portal-keeper remains active up to sequence number $L$ and then goes permanently silent while toroidal messages continue to $M > L$. The lifetime-ratio guard stays **completely blind** for the entire silent stretch

$$L < M \le \left\lfloor \frac{20}{7} L \right\rfloor,$$

whose silent gap grows linearly with swarm age: $\Delta_{\text{blind}}(L) = \lfloor \frac{13}{7} L \rfloor = \Omega(L)$.

**Exact Empirical Witness (`M = 1,677` messages):**

- Cartographer stops at $L = 1{,}298$; weaver stops at $W_{\text{last}} = 1{,}523$.
- Legacy lifetime-ratio check (exact cross-multiplication):
  $$20 \cdot L = 20 \cdot 1{,}298 = 25{,}960 \;\ge\; 11{,}739 = 7 \cdot 1{,}677,$$
  so `CS-01` reports **`CLEAR (risk=0)`** even though the cartographer has been silent for **`379` consecutive messages** (`gap = 1,677 - 1,298 = 379`), the weaver has been silent for **`154` consecutive messages**, and the trailing `50`-message sliding window contains **`0`** poloidal messages ($\iota_{50} = 0$).
- Worse, under the lifetime rule, once $L = 1{,}298$, the cartographer could remain silent until $M = 3{,}708$ (`2,410` consecutive silent messages!) before `CS-01` would fire.

---

## 2. The Continual Rotational-Transform Law ($\iota_W > 0$)

For any trailing sliding window of length $W_{\text{eff}} = \min(W, N)$ over the `seq`-ordered board messages ($W \ge 1$ exact integer, default $W = 50$), define the exact rational **sliding-window rotational transform**:

$$\iota_W := \frac{P_W}{W_{\text{eff}}} \in \mathbb{Q} \cap [0, 1],$$

where $P_W$ is the count of poloidal messages (`cartographer`, `portal-keeper`, `portal_keeper`, `weaver`, `synthesizer`) inside the trailing window. Given an exact rational floor $p/q$ ($1 \le p \le q$, default $1/25$), continual flow requires ALL THREE exact integer inequalities simultaneously:

1. **Positive Sliding-Window Winding (division-free cross-multiplication):**
   $$P_W \cdot q \;\ge\; W_{\text{eff}} \cdot p.$$
2. **Bounded Cartographer & Weaver Silence Gaps:**
   $$M - L_{\text{cart}} \;\le\; G_{\text{cart}} \quad (\text{default } 40), \qquad M - L_{\text{weaver}} \;\le\; G_{\text{weaver}} \quad (\text{default } 60).$$
3. **Optional Pure-Integer Wall-Clock Silence Cap ($T_{\max} \ge 1$ seconds):**
   $$t(M) - t(L_{\text{cart}}) \;\le\; T_{\max},$$
   computed strictly in integer UTC seconds (`delta.days * 86400 + delta.seconds`, zero IEEE-754 floats).

Unlike a lifetime ratio, these three conditions are **shift-invariant in swarm length $M$**: regardless of whether a swarm is at message `50` or message `50,000`, halting poloidal feedback trips `CS-01` within at most `min(G_cart, W)` messages.

---

## 3. Formal Specifications of Hardened `CS-01`, `CS-22`, and `CS-23`

All three detectors are implemented in `aletheia/flow_audit.py` using bounded, symlink-refusing (`O_RDONLY | O_DIRECTORY | O_NOFOLLOW` ancestor walk + `O_RDONLY | O_NOFOLLOW | O_NONBLOCK` leaf + `fstat` `S_ISREG` + `64 KiB` streaming read chunks) and zero-float strict JSON parsing (`aletheia.strict_io.loads_strict_json(..., allow_float=False, require_object=True)`), returning the exact `aletheia/diagnose.py` pattern schema (`id`, `name`, `risk_score`, `status`, `evidence`, `remediation`).

### 3.1 Hardened `CS-01` — Static-Map Trap (Continual Rotational-Transform Gate)

| Condition | Risk Increment | Notes |
|---|---:|---|
| Missing `frontier_portals.md` | `+50` | Immediate `ALERT` when portal map absent |
| Zero cartographer/portal-keeper posts on non-empty board | `+50` | Never wound |
| `max_seq - last_cartographer_seq > max_cartographer_gap` | `+45` | Also sets `legacy_lifetime_blind_spot = True` when `max_seq >= 8` and `20 * last_cart_seq >= 7 * max_seq` |
| `max_seq - last_weaver_seq > max_weaver_gap` (or 0 weaver posts with `N > max_weaver_gap`) | `+25` | Detects uncoupled weaving |
| `poloidal_in_window * min_poloidal_den < window_len * min_poloidal_num` | `+40` | Exact cross-multiplied $\iota_W < p/q$ gate |
| Optional `cartographer_silence_seconds > max_silence_seconds` | `+35` | Pure-int UTC seconds |

Risk is clamped to `[0, 100]` (`>= 50` $\to$ `ALERT`, `>= 20` $\to$ `WARNING`, `< 20` $\to$ `CLEAR`).

### 3.2 `CS-22` — Hardening Treadmill / Stranded-Verification Drift

Parses `verification/AUDIT_LOG.md` (both markdown table rows and section blocks) alongside the trailing board window and optional `frontier_portals.md` / atlas:

- **Re-Hardening Pressure vs. Synthesis (`hardening_pressure = rehardening_audits + tail_hardening_posts`):**
  - `+40` when `hardening_pressure >= 3` and `tail_synthesis_posts == 0`;
  - `+25` when `hardening_pressure >= 4` and `hardening_pressure > 3 * tail_synthesis_posts` (pure-integer `> 3x` ratio).
- **Stranded Locally Verified Tracks:** Tracks marked `VERIFIED` (whole-token, excluding `NOT VERIFIED`, `UNVERIFIED`, `FALSIFIED`, `PARTIAL/FRAGILE`) that have **`0` references** in `frontier_portals.md` / atlas **and** **`0` external PR/issue shipment links**:
  - `+40` when `len(stranded_tracks) >= 3`;
  - `+20` when `1 <= len(stranded_tracks) < 3`.

### 3.3 `CS-23` — Swarm-Flow Resonance Amnesia (Unfolded Inter-Agent Data Flows)

Defines `last_fold_seq` as the latest `seq` authored by a folding role (`cartographer`, `portal-keeper`, `portal_keeper`, `synthesizer`), or `0` if none exists, and scans the exact **unfolded tail window** `[last_fold_seq + 1, max_seq]`:

- Extracts deterministic candidate cross-track signals absent from `frontier_portals.md` and `atlas_file`:
  1. `frozen_track`: track identifiers (`Track S<id>` / `track-s<id>`) not yet referenced in portals or atlas;
  2. `exact_operator`: canonical exact operators (`Schur`, `Krein`, `Hodge`, `Frobenius`, `Landauer`, `Burnside`, `CS-20`, `CS-21`, `8-glyph`, `Sylvester-inertia`, `Sherman-Morrison`, `Construction-A`, `MacWilliams`) present in the unfolded tail but absent from portals/atlas;
  3. `obstruction_or_anomaly`: structured finding/seam IDs and named obstructions/anomalies/blind-spots/counterexamples absent from portals/atlas.
- Emits exact `unfolded_window: [start, end]`, `unfolded_message_count`, sorted canonical `missed_signals`, and deterministic `missed_signals_sha256`.
- Risk mapping: `>= 3` missed signals $\to$ `80` (`unfolded_count >= max_cartographer_gap`) or `55`; `1..2` missed signals $\to$ `50` (`unfolded_count >= max_cartographer_gap`) or `25`; `0` missed signals with `unfolded_count > max_cartographer_gap` $\to$ `25`; otherwise `0` (`CLEAR`).

---

## 4. Integration Plan with `aletheia diagnose` & `MAGNETIC_FIELD_V21.md`

1. **Zero-Conflict Phase (This PR):** Ships `aletheia/flow_audit.py`, `spec/proposals/CONTINUAL_TOROID_FLOW.md`, and `tests/test_continual_toroid_flow_r5.py` with zero edits to `aletheia/diagnose.py` or `aletheia/cli.py`, keeping merge-tree compatibility with all concurrent core fixes and `spec/proposals/MAGNETIC_FIELD_V21.md` (`zone_b_fuzzer`, `claim_witness`, `magnetic_field_v21`).
2. **Thin Wiring Follow-Up (Post-Merge):**
   - Call `check_continual_flow_patterns(...)` from `aletheia/diagnose.py` to upgrade `CS-01` in place and append `CS-22` and `CS-23` into the `aletheia diagnose` pattern list;
   - Expose `aletheia flow-audit` alongside the planned `aletheia zone-b-fuzz` / `aletheia claim-witness` / `aletheia pre-push-gate` CLI subcommands from `spec/proposals/MAGNETIC_FIELD_V21.md`;
   - Couple `CS-23`'s `missed_signals` digest directly with `magnetic_field_v21.compute_field_coupling_dispatch` so unfolded cross-track signals automatically feed omni-vein dispatch instead of drifting out of sight.

---

## 5. Verification Commands (Canonical 3-Mode Isolated R4 Parity + Hash-Seed Check)

```bash
# Built-in deterministic self-test across the 3 canonical isolated R4 modes
python3 -I -B aletheia/flow_audit.py --self-test --json
python3 -I -O -B aletheia/flow_audit.py --self-test --json
python3 -I -B -W error aletheia/flow_audit.py --self-test --json

# Standalone CLI against an expedition workspace and board JSONL
python3 -I -B aletheia/flow_audit.py /path/to/expedition \
  --board /path/to/board.jsonl \
  --portals-path /path/to/frontier_portals.md \
  --window 50 --max-gap 40 --json
python3 -s -B -m aletheia.flow_audit /path/to/expedition \
  --board /path/to/board.jsonl \
  --portals-path /path/to/frontier_portals.md \
  --window 50 --max-gap 40 --json

# Test suite across the 3 canonical isolated R4 modes + hash-seed parity
python3 -I -B tests/test_continual_toroid_flow_r5.py
python3 -I -O -B tests/test_continual_toroid_flow_r5.py
python3 -I -B -W error tests/test_continual_toroid_flow_r5.py
PYTHONHASHSEED=42 python3 -B tests/test_continual_toroid_flow_r5.py
```
