# Proposal: Two-Zone Blinded Airlock, `ClaimLedger` Outcome Binding & Erlang/OTP Supervision Semantics

**Status:** Proposal, not adopted. Adoption is for the method's maintainers. Written against `aletheia.spec.v2.0` (`spec/LAWS_AND_GATES.md`), harmonized directly with `spec/proposals/EMPIRICAL_CLAIMS.md` (`aletheia#10 @ bf37ea73`), and backed by dual-family verified formal pure-$\mathbb{Z}/\mathbb{Q}$ airlock/non-interference and OTP supervision studies (`N0` over `Moissanite-Labs/exo#934`, `aletheia#10`, Armstrong 2003 / Erlang/OTP `supervisor.erl` & `exo#1200` + `N1` engineering/audit pure-$\mathbb{Z}/\mathbb{Q}$ supervision-tree certifier).  
**Reference Implementation:** [`aletheia/supervision_airlock.py`](../../aletheia/supervision_airlock.py), verified by [`tests/test_supervision_airlock_r5.py`](../../tests/test_supervision_airlock_r5.py).

---

## 1. Purpose & Alignment With `EMPIRICAL_CLAIMS.md` (`aletheia#10`)

The `EMPIRICAL_CLAIMS.md` proposal (`aletheia#10 @ bf37ea73`) explicitly leaves two follow-up mechanisms for separate proposals:

1. **Binding each prose claim to its computed outcome** (preventing reports or summaries from stating a stronger verdict or evidence grade than the checked computation supports).
2. **A blinded verifier that receives only the claim, the pinned inputs, and the code** (preventing social agreement, model prestige, or persuasive deliberation in discovery rooms from biasing verification).

When multi-agent discovery and verification run concurrently, a third operational hazard arises: **mid-audit snapshot churn and collateral verifier failure** (restarting an author while downstream verifiers still audit an obsolete artifact digest, or linking a verifier so a verifier crash kills the coordinator). This proposal pairs the **Two-Zone Blinded Airlock + `ClaimLedger`** with **Erlang/OTP Supervision Tree Semantics** as a single composable v2.1 architectural pack.

---

## 2. Two-Zone Hybrid Airlock & `ClaimLedger` Outcome Binding

```text
Zone A: Socratic Discovery Room          Airlock (M03 Strip)          Zone B: Blinded Verifier Chamber
+---------------------------------+     +-----------------------+     +--------------------------------+
| mode="socratic", conductor=None |     | ONLY (deep-copied):   |     | channel_mode="private_c02"     |
| >=2 unique participants         |---->|  - claim_ledger (N0)  |---->| verifier_seat not in Zone A    |
| round_robin_enforced=False (S03)|     |  - pinned_inputs+seeds|     | read_scope=[envelope_id] (M05) |
| silent_turns_allowed=True (G08) |     |  - artifact_bundle    |     | 7 blocked channels (bus/peers) |
| >=2 distinct hypotheses         |     |                       |     | can_read_zone_a_board=False    |
| output_tag=UNVERIFIED_HYPOTHESIS|     | STRIPS: transcript,   |     | can_approve_own_changes=False  |
| agreement_counted_as_ev=False   |     | authors, models,      |     | write_scopes=[] (I15 read-only)|
+---------------------------------+     | votes, agreement_cnt  |     +---------------+----------------+
                                        +-----------------------+                     |
                                                                                      v
                                                                      Structured Verdict Packet:
                                                                      envelope_sha256 + Part E verdict +
                                                                      Part I grade + outcome_matched +
                                                                      R5 counts + minimal counterexample
```

### 2.1 Fail-Closed Airlock & `ClaimLedger` Contracts

Implemented by `strip_zone_a_to_airlock_envelope`, `validate_airlock_envelope`, `certify_two_zone_airlock`, and `verify_observational_non_interference` in `aletheia/supervision_airlock.py`:

1. **M03 Deep-Copy Stripper & Observational Non-Interference:**
   - Projects a Zone-A submission strictly onto `{schema, envelope_id, claim_ledger, pinned_inputs, artifact_bundle}` via deep copy (zero mutable aliasing).
   - Recursively rejects any nested dict key matching the `15` forbidden social/persuasion keys (`transcript`, `board_messages`, `author`, `authors`, `model`, `models`, `agreement_count`, `votes`, `consensus`, `persuasion`, `socratic_log`, `seat_name`, `deliberation`, `chat_history`, `zone_a_messages`), any non-string dict key, and any IEEE-754 float.
   - `verify_observational_non_interference(room_1, room_2)` certifies that two Zone-A rooms with strictly distinct `transcript`, `authors`, `models`, and `agreement_count` but identical technical submissions strip to **both-valid, byte-identical** Zone-B envelopes. The blinding claim is scoped to **no social keys crossing the airlock** (closed keysets + forbidden-key scan); free-text values are not content-filtered beyond the charset/length caps above.
2. **`ClaimLedger` Prose-to-Outcome Binding (Harmonized with `EMPIRICAL_CLAIMS.md`):**
   - `claim_ledger` pins `claim_id`, `finite_outcome_grammar` (`>= 2` unique trimmed control-free tokens), non-empty `falsifier_predicate`, mandatory `novelty_default == "N0"`, and `linguistic_ceiling` over the `EMPIRICAL_CLAIMS.md` Part-I ladder (`E0_LEAD`, `E1_PLANNED`, `E2_SEALED`, `E3_REIMPLEMENTED`, `E4_REPLICATED`, `E5_OUTSIDE_REPLICATED`).
   - Returned `verdict_packet` (`aletheia.airlock_verdict.v1`) binds `envelope_sha256`, `verifier_seat`, `part_e_verdict` (`VERIFIED`, `PARTIAL_FRAGILE`, `FALSIFIED`, `NOT_SHOWN`), `part_i_grade` (ladder or `EXACT_ONLY_NA`), `outcome_matched`, `r5_killed`/`r5_total`, and `counterexample`:
     - `finite_outcome_grammar` is a **polarity-declaring dict** `{token: "supports"|"against"|"inconclusive"}` (2..64 unique clean-ASCII tokens, <=64 chars each) — not a bare list, so the ledger declares each token's polarity instead of the certifier guessing from denylist strings.
     - `outcome_matched` MUST belong to the declared grammar and its declared polarity MUST NOT contradict `part_e_verdict`: `VERIFIED` requires polarity `supports`; `PARTIAL_FRAGILE`/`FALSIFIED`/`NOT_SHOWN` forbid polarity `supports` (`inconclusive` contradicts neither).
     - `part_i_grade` (when not `EXACT_ONLY_NA`) MUST NOT exceed `claim_ledger.linguistic_ceiling`, and non-`VERIFIED` verdicts (`PARTIAL_FRAGILE`, `FALSIFIED`, `NOT_SHOWN`) are capped at `E0_LEAD` (or `EXACT_ONLY_NA`). **Deliberate divergence from `EMPIRICAL_CLAIMS.md:205`** ("a sealed run keeps its grade whatever the outcome"): that rule governs claim-evidence grades; this airlock additionally caps the *verdict-packet* Part-I grade at `E0_LEAD` for adverse verdicts, because a falsified claim must not carry an elevated evidence grade inside a blinded-verifier packet. The two rules compose: the underlying run keeps its grade, the packet does not claim it.
     - `VERIFIED` requires `r5_killed == r5_total >= 10` (mutation floor — a 1/1 run is not evidence) and `counterexample is None`; any non-`VERIFIED` verdict requires a non-empty clean-ASCII minimal `counterexample`.
     - Content rules (defense-in-depth; the airlock blinds KEYS, not free-text values): `falsifier_predicate` must be clean ASCII and <= 4096 chars; artifact `relpath`s must match `[A-Za-z0-9_./-]+` with no `.`/`..`/empty components.
3. **Zone-B Isolation (`C02`, `M05`, `C05`, `I15`, `R3`):**
   - Requires `channel_mode == "private_c02"`, `verifier_seat.lower() not in {p.lower() for p in zone_a.participants}` (a **string-inequality check** — identity is unverifiable in a declared record), `read_scope == [envelope_id]`, all `7` mandatory blocked channels (`bus`, `memory`, `peers`, `peer_send`, `bus_post`, `send_message`, `zone_a_board`), `can_read_zone_a_board is False`, `can_approve_own_changes is False`, and `write_scopes == []`.

---

## 3. Erlang/OTP Supervision Tree Semantics & Frozen-Snapshot Non-Churn

Implemented by `otp_should_restart`, `apply_otp_strategy_crash`, `verify_snapshot_non_churn`, `certify_restart_intensity_trace`, `certify_monitor_vs_link_isolation`, and `decide_hybrid_supervision` in `aletheia/supervision_airlock.py`:

1. **Exact $3 \times 3$ Restart Policy Matrix (`otp_should_restart`):**
   - `permanent` restarts on `{normal, shutdown, abnormal}`; `transient` restarts iff `exit_reason == "abnormal"`; `temporary` never restarts (`4` restart, `5` drop).
2. **Ordered Supervision Strategies & Frozen-Snapshot `rest_for_one` Non-Churn (`apply_otp_strategy_crash`, `verify_snapshot_non_churn`):**
   - Models `one_for_one`, `one_for_all`, and `rest_for_one` with exact reverse-start-order termination and forward-start-order restart, strictly validating child schemas/IDs/non-uniform digests and obeying OTP `supervisor.erl` non-resurrection rules: `temporary` children are never restarted, already-dead `transient` siblings are never resurrected during sibling-triggered restarts, and `permanent` children cannot start dead (`ERR_DEAD_PERMANENT_CHILD`).
   - For an ordered Zone-A/Airlock pipeline `[planner, author, airlock_snapshot, verifier_a, verifier_b]`, `rest_for_one` tears down and re-binds all downstream consumers to the new immutable `snapshot_sha256` (`stale_downstream_count == 0`, with non-empty unique `downstream_ids` and an alive `author`) without restarting upstream `planner`, whereas `one_for_one` triggers `ERR_SNAPSHOT_CHURN`.
3. **Pure-$\mathbb{Z}/\mathbb{Q}$ Inclusive Sliding-Window Restart Intensity (`certify_restart_intensity_trace`):**
   - Retains restarts satisfying exact rational inequality $t_{\mathrm{now}} - t \le W$ (`Fraction`, zero IEEE-754 rounding drift on non-dyadic windows such as `1/3`), rejects backward timestamps (`ERR_NON_MONOTONIC_TICK`), escalates to `MAX_RESTART_INTENSITY_EXCEEDED` iff $|\text{active}| > \text{max\_restarts}$, and fails closed on any trailing crash event after escalation (`ERR_EVENT_AFTER_ESCALATION`).
4. **Asymmetric Fault-Isolation Theorem (`certify_monitor_vs_link_isolation`):**
   - Compares unidirectional `monitor` against bidirectional `link` (`trap_exit=False` and `trap_exit=True`). Because OTP `kill` bypasses `trap_exit=True` on linked processes and cascades `"killed"` to siblings, **unidirectional `monitor` is strictly stronger than `link + trap_exit=True`** (`0` collateral kills vs. `2` collateral kills) and is mandatory for Zone-B clean-room verifiers.
5. **Safety-Dominance Composition With `exo#1200` (`decide_hybrid_supervision`):**
   - Validates `task_state` against the closed `exo#1200` state enum (`pending`, `running`, `failed`, `completed`, `stopped`, `cancelled`, `uncertain`); sticky stop (`stop_requested=True` or `task_state in {"stopped", "cancelled"}`), terminal failure classes (`cancelled`, `denied`, `spend_limit`, `permanent`), and post-dispatch effects (`effect_class != "not_dispatched"`) unconditionally override OTP restart rules; only a pre-dispatch `transient` failure within lifetime `max_retries` may consult OTP restart policy.

---

## 4. Honest Scope Boundaries & Non-Claims

1. **Declared-Record / Formal-Model Boundary:** Consistent with `spec/LAWS_AND_GATES.md` and `EMPIRICAL_CLAIMS.md`, `aletheia/supervision_airlock.py` certifies caller-supplied airlock envelopes, verdict packets, and discrete finite-state supervision traces in pure Python; it does **not** prove OS-level process sandboxing, BEAM VM scheduler timing, or live multi-host SQLite crash recovery.
2. **Not an OS Sandbox:** Engine-level audience rules (`M05`, `C02`) and lexical `write_scopes == []` checks do not isolate agents that share unrestricted host shell access.
3. **Honest Novelty Standing (Law 4):** `N0` for all classical Erlang/OTP semantics (Armstrong 2003; `supervisor.erl`), `Moissanite-Labs/exo#934`/`#1200`, and `EMPIRICAL_CLAIMS.md`; `N1` (engineering/audit) strictly for the executable pure-$\mathbb{Z}/\mathbb{Q}$ airlock/supervision certifier composition and Frozen-Snapshot `rest_for_one` Non-Churn witness.
