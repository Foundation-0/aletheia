# Proposal: give empirical claims an exact core

**Status:** Proposal, not adopted. Adoption is for the method's maintainers. Written against `aletheia.spec.v2.0` as it stands on the open v2 pull request.

## The limit

An exact claim is closed by computation. Exact arithmetic decides it, a second checker that shares no code decides it again, and must-fail controls show that both checkers can say no.

An empirical claim has one step that no computation closes: the step from the data to the world. The data could come from a faulty instrument, a biased sample, or a pattern that will not recur. No amount of checking the code removes that.

So empirical claims cannot reach the same infallibility as exact ones. A method that says they can will overclaim. Two things can be reached:

1. Make every part of the claim except that one step exact.
2. Put a stated, tested bound on how often that step is wrong, and say which assumptions the bound rests on.

## The split: every empirical claim has two parts

**Part E (exact).** "Procedure P, fixed in advance and stored at hash `h(P)`, run on these bytes (hash `H`) with these seeds, returns outcome `O`." This is a statement about a finite computation. It is true or false, and it gets the full exact treatment: bit-for-bit rerun, a second implementation, must-fail controls, and the three Python modes of R4.

**Part I (inferential).** "P is wrong about the world at most this often, under these stated assumptions." This is never `VERIFIED`. It earns a grade (below) for what it has survived, and each grade lists what it has not yet survived.

This fits the oracle classes in section 2.2 of `spec/LAWS_AND_GATES.md`. Part E is an `exact` claim about a computation, even when P uses random draws, because the seeds are part of the statement. Part I stays `sampled`, as the spec requires: "exact arithmetic is not an exact oracle." The split makes that line visible in every claim instead of leaving it to the reader.

It also fits Own-Terms-First (section 1.1). Predicting sealed, unseen data with a rule fixed in advance needs no particular notation and no existing theorem. A pattern written in the team's own symbols can pass or fail it on equal terms. It is the test that stays valid if existing mathematics is the constraint.

### The exact side needs the same discipline

Exact gates are only as strong as their certifiers. A gate that reads declared numbers instead of recomputing them is not a gate.

The open review of the v2 pull request found this in the Law 2b gate, which checks a residual ceiling the submitter picks. The Own-Terms-First certifier has the same shape: it compares observed and null scores passed in by the caller and does not compute them from data (as of commit 0b60322, later commits changed some of this).

Contract R7 ("measured, not declared") already states the rule. This proposal applies R7 to every empirical gate below.

## A claim record, in short

```text
claim:        "<the pattern, in the authors' own terms>"
part_E:       procedure P at plan hash h(P), run on manifest hash H,
              seeds S, returns outcome O            -> VERIFIED or not
part_I:       P is wrong about the world at most a, assuming A1..An
grade:        E2 SEALED_PASS
not_survived: second implementation, independent instrument
scope:        instrument X, 2019-2023, band 0.1-10 Hz
novelty:      N0 (full-text prior work not yet read)
ledger:       41 runs, head entry hash ...
```

## How to read the gates

Each gate has four fields:

- **Rule:** what the claim must do.
- **Catches:** the failure it is there to stop.
- **Certifier recomputes:** what a checking program computes from the bytes, rather than reading from a declaration.
- **Must-fail control:** a deliberately broken input that the certifier must refuse. A certifier with no must-fail control is not counted (R5).

A fifth line, **In v2 now**, says what the current spec already requires. Where v2 covers a point, only the difference is proposed.

Gates 1 and 3 are R6 and R7 applied to data. Gates 2, 5, 6 and 9 are the null and mutation discipline of Gates 3 and 7 moved earlier, before any data file is opened.

## The twelve gates

### 1. Plan before data

- **Rule:** The claim is a decision procedure frozen before any data file is opened.
  - The plan fixes the tests, the family of tests over which errors are controlled, the thresholds and the seeds.
  - It holds an outcome table that maps every reachable combination of test results to exactly one outcome.
  - The plan's hash is anchored outside the authors' control before the data is fetched: a public timestamp, or a commit in a repository the authors cannot rewrite.
  - Later changes are dated amendments that quote the text they replace.
- **Catches:** Choosing the test, the threshold or the reading of a result after seeing the data. Outcome tables with gaps or overlaps, where a result can be read two ways.
- **Certifier recomputes:** The plan hash, and checks that the external anchor predates the first entry in the fetch manifest and the run ledger (gate 10). Enumerates every reachable state of the test results and checks that each maps to exactly one outcome. Diffs each amendment against the quoted text.
- **Must-fail control:** A plan with one state mapped to two outcomes, a plan with one state unmapped, and a plan whose anchor is dated after the fetch. Each must be refused.
- **In v2 now:** Gate 8 requires preregistrations to be committed and hashed before reading code or data, and keeps every miss. Not yet required: an anchor outside the authors' control, an outcome table checked by enumeration, and amendments that quote the old text.

### 2. Calibrate the instrument before data (known-answer tests)

- **Rule:** Before any data file is opened, the detector runs on synthetic series with known answers. It must find planted effects at a stated power. It must stay at its nominal false-alarm rate on matched nulls, including nulls that differ from the signal only in the claimed property. Each known-answer test has a deliberately wrong control that must be flagged. No data file is opened until every test passes.
  - A known-answer script exits non-zero when it fails. Production gates carry no bypass switch. Calibration inputs include tied and constant data wherever the real data can contain ties.
- **Catches:** A detector that sees the claimed property in data that lack it, or misses it where it is planted. These failures are cheap to find on synthetic data and expensive to find after a verdict.
- **Certifier recomputes:** Reruns the known-answer suite from the seeds in the plan, counts hits and false alarms, and compares them with exact binomial bounds pinned in the plan.
- **Must-fail control:** A detector that always reports "present", and one with a known defect, must each fail the suite.
- **In v2 now:** The empirical domain pack lists a seven-rung null hierarchy and planted-signal recovery. Not yet required: that calibration happens before data, with a stated power, a pinned bound, and a block on opening data until it passes.
- **Worked example:** In the cave-expedition [pre-registration](https://github.com/Foundation-0/cave-expedition/pull/6), the first frozen plan failed four of its six [known-answer tests](https://github.com/Foundation-0/cave-expedition/pull/8) before any data file was opened. False-alarm rates reached 0.295 after a monotone map (`exp`).

  In the review of cave-expedition pull request 8, a rank step that broke ties in time order turned a perfectly symmetric tied waveform into an apparent time arrow, and the calibration had missed it because it used only tie-free noise.

  The plan was then amended, still before any data was opened. A checker that shared no code with the author checked the amendment.

### 3. Bytes, not summaries

- **Rule:** Raw data are pinned by hash from the primary archive, with a fetch manifest (source URL, retrieval date, size, hash). Every number in a claim is regenerated from those bytes by code in the repository. A number the repository cannot regenerate is not a claim.
- **Catches:** Figures copied from a notebook, a pull request body or a stored certificate that no longer match the code. Silent changes to upstream files.
- **Certifier recomputes:** Hashes every file against the manifest, runs the regeneration script, and compares every number in the claim file with the regenerated value. The comparison is exact on rationals or on fixed decimal strings, never a float tolerance.
- **Must-fail control:** A claim file with one number changed in its last digit, and a manifest with one wrong hash. Both must be refused.
- **In v2 now:** R7 states the principle for gates. Gate 1 requires clean-room replay. Not yet required: a fetch manifest, and a rule that every number in an empirical claim is regenerated.
- **Applies to reviewers:** The same rule binds reviewers. This week an outside review that doubted a pull request's numbers without recomputing them from the source texts was withdrawn for that reason, and its replacement will recompute first.

### 4. A holdout that is really unseen

- **Rule:** The data are split into a development part and a sealed part.
  - The split is fixed by a rule over identifiers (for example, a salted hash of each record's identifier), written in the plan before anyone looks.
  - The sealed part is opened once, for one verdict run, and the opening is logged.
  - Data used during development is not held out.
  - Where practical, the sealed part is stored encrypted, with the key held by someone outside the authoring team.
  - Two cases are kept apart. A sealed holdout proper is data released after the plan's anchor date, or held by a party outside the authors until the verdict run.
  - Data already in a public archive cannot be sealed. For it, the split is fixed by a salted rule over identifiers, every run is in the ledger, and a clean-room rerun is required. This cannot prevent an earlier look, so it is a lower assurance, and the claim record says which case applies.
  - A split-half of data already used (for example odd and even items) is an internal-consistency check, not a holdout.
- **Catches:** "Held-out" data that the authors inspected while designing the test. A verdict run repeated until it passes.
- **Certifier recomputes:** The split from the identifier list and the salt in the plan. Checks in the run ledger that no entry before the verdict run touched a sealed identifier, and that exactly one verdict run exists.
- **Must-fail control:** A ledger with one development run that reads a sealed record, and a ledger with two verdict runs. Both must be refused.
- **In v2 now:** Gate 6 requires re-testing on unseen draws without re-tuning. Own-Terms-First Phase 1 requires data the finder never saw. Not yet required: a split rule fixed in advance, a single logged opening, and a check that recomputes both.

### 5. Exact error accounting

- **Rule:** Every error rate in the claim is computed, not assumed.
  - Each test's null distribution is exact (full permutation, exact binomial) or calibrated by simulation under gate 2.
  - With `m` random permutations, the p-value is `(1 + b) / (1 + m)`, where `b` counts null draws at least as extreme as the observed value. This is valid for any `m`.
  - The p-value above is exact only when the null draws are exchangeable with the data under the null (permutations, sign flips). Surrogate nulls that preserve a spectrum are approximate, and count only with a passing calibration under gate 2 on the same pipeline. Each test records which kind it uses.
  - P-values and levels are integers or exact rationals, never floats. The float 0.05 is slightly larger than 1/20 and can flip a boundary decision.
  - Nulls use many draws, never a single shuffle.
  - The smallest attainable p-value of each test is computed in the plan. A test that can never reach its level is removed before data.
  - The whole confirmatory family is corrected together.
  - The chance that the outcome is a false positive is stated as a number at every step of the correction, not only at the most favourable one.
- **Catches:** Tests that cannot reject by design. One-shuffle nulls with no interval. Families corrected piecemeal. Reports that quote only the best adjusted p-value.
- **Certifier recomputes:** The smallest attainable p-value for each test (for example `1 / (1 + m)` for a permutation test, so Bonferroni over `k` tests at level `a` needs `m >= k / a - 1`). Every p-value from the stored null draws. Every adjusted p-value in the correction, compared with the claim.
- **Must-fail control:** A plan with a test whose smallest attainable p-value exceeds its share of the level, and a result computed from one null draw. Both must be refused.
- **In v2 now:** Own-Terms-First uses Bonferroni across pinned nets. The domain pack asks for at least 200 surrogates with rank p-values for single-shot detection. Not yet required: the smallest attainable p-value in the plan, one correction over the whole family, and a stated bound at every step. The current Own-Terms-First certifier takes one null score per net, not a null distribution.

### 6. Invariance and controls on the real data

- **Rule:** The result must not change under transformations that should not matter (units, monotone maps, resampling choices the plan declares irrelevant). It must vanish under transformations that should destroy it (shuffled order, broken pairing). Positive control: inject a synthetic effect of known size into the real data and recover it. Negative control: a channel or epoch where the effect must be absent.
- **Catches:** Artefacts of scale, units or window. Detectors that respond to something other than the claimed property. A pipeline that would miss a real effect in this particular data.
- **Certifier recomputes:** Runs the pipeline under each declared transformation, each destroying transformation, each injection and each negative control, and compares outcomes with the plan's expected outcomes.
- **Must-fail control:** A detector known to depend on raw scale (for example, a linear correlation after an `exp` map) must fail the monotone-map check.
- **In v2 now:** Gate 2 and Own-Terms-First net invariance cover transformations that should not matter. Own-Terms-First Rule 5 covers negative controls. Not yet required: destroying transformations, and injection into the real data.

### 7. Second implementation

- **Rule:** A clean-room re-implementation, written from the plan text alone and sharing no code, reaches the same outcome on the same bytes.
- **Catches:** Bugs in the pipeline. Plans that only make sense with the author's code beside them. A disagreement shows where the plan text is ambiguous.
- **Certifier recomputes:** Both outcomes from the two pinned commits. Checks that neither implementation imports or copies files from the other (no shared file hashes, no cross imports).
- **Must-fail control:** A "second" implementation that imports a module of the first must be refused.
- **In v2 now:** Law 3 requires zero-shared-code verification across bases. Not yet required for empirical claims: that the second implementation starts from the plan text and not from the first implementation.

### 8. Replication on independent data

- **Rule:** The unchanged plan runs on data from a different instrument, epoch or source. Independence means a different source lineage (instrument or corpus, epoch or edition, channel), not different file hashes. Re-encodings, resamplings and translations of one source do not count. Agreement between pipelines (gate 7) catches bugs. Agreement between instruments catches artefacts.
- **Catches:** Instrument artefacts, processing artefacts in one archive, and patterns tied to one period.
- **Certifier recomputes:** The plan hash on both runs (they must match), the manifests of both datasets, and the outcome of each run.
- **Must-fail control:** The same bytes relabelled as an independent dataset (overlapping file hashes) must be refused.
- **In v2 now:** Own-Terms-First Phase 1 requires a second instrument. Not yet required: an unchanged plan hash, and a byte-level independence check.

### 9. Mutation testing of the safeguards

- **Rule:** Remove each guard in turn and confirm that some test fails. A guard no test defends is not a guard. Also run the whole pipeline on a deliberately false version of the claim (shuffled labels, time-reversed data) and confirm that it does not confirm that too.
- **Catches:** Refusals that exist in the code but are never exercised. Pipelines that report "supported" for any input.
- **Certifier recomputes:** The mutation run (`aletheia mutate`), and the false-claim runs with seeds from the plan.
- **Must-fail control:** A pipeline with one guard removed must be caught. A pipeline that returns "supported" on shuffled labels must be refused.
- **In v2 now:** R5 and `aletheia mutate` cover guard removal. Not yet required: the false-claim run on the whole pipeline.

### 10. The full denominator

- **Rule:** An append-only run ledger records every analysis run against the data. Each entry holds the time, code commit, plan hash, data hashes read, output hash, and the hash of the previous entry. The number of attempts behind a reported result can then be checked. Failed and partial results stay on record.
- **Catches:** Selective reporting, where many analyses were run and one is shown.
- **Certifier recomputes:** The hash chain, the count of runs, and a link from every reported result to its ledger entry.
- **Must-fail control:** A ledger with a middle entry deleted, and a reported result with no ledger entry. Both must be refused.
- **In v2 now:** Gate 8 keeps every preregistration miss. Not yet required: a ledger of every run, with a chain a certifier can verify.
- **Limit:** The ledger only counts what passes through it. A copy of the data analysed elsewhere leaves no trace. The encrypted holdout of gate 4 is what makes the count enforceable for the verdict run.

### 11. An advocate before any adverse or narrowing verdict

- **Rule:** Before an adverse or narrowing verdict is final, the claim's authors argue for it first. Then a reviewer argues for it who took no part in writing or checking, shares no code with the pipeline, and was named before the outcome was known.
- **Catches:** Verdicts that rest on one checker's reading, and adverse results caused by a pipeline bug rather than by the world.
- **Certifier recomputes:** That the reviewer was named in a commit dated before the verdict run, that the reviewer has no commits in the pipeline, and that a ruling (`stands`, `stands_narrowed`, `falls`) is recorded for each adverse or narrowing verdict.
- **Must-fail control:** A reviewer named after the verdict run must be refused.
- **Open:** What counts as independent for a reviewer inside the same organisation is left open here, pending a ruling by the repository owners.
- **In v2 now:** Gate 10, Law 2 and Law 2b cover most of this. Not yet required: naming the reviewer before the outcome, and the authors' turn first.

### 12. Scope

- **Rule:** Each claim states the instruments, ranges and populations it covers. Extending it beyond them is a new claim, starting at the lowest grade.
- **Catches:** A result on one instrument or range quoted as a general law.
- **Certifier recomputes:** The ranges actually covered by the pinned bytes (time span, frequency band, sample population) and checks that the stated scope does not exceed them.
- **Must-fail control:** A claim whose stated scope is wider than its data must be refused.
- **In v2 now:** Law 4 requires scope boundaries. Not yet required: recomputing scope from the bytes, and the new-claim rule for extensions.

## Grades for Part I

Part E is judged with the existing verdicts (`VERIFIED`, `PARTIAL/FRAGILE`, `FALSIFIED`, `NOT_SHOWN`). Part I gets a grade instead. The names below follow the `N0` to `N2` pattern of the novelty scale. A grade is a record of what the claim has survived, never a verdict that it is true.

| Grade | Needs | Has survived | Has not yet survived |
|---|---|---|---|
| `E0 LEAD` | Nothing | Someone saw a pattern | Any test fixed in advance |
| `E1 PLANNED` | Gates 1, 2, 3 | A frozen plan, a calibrated detector, pinned bytes | Contact with sealed data |
| `E2 SEALED_PASS` | Gates 4, 5, 6, 10 | One sealed run with exact error accounting and controls | A second implementation, other data |
| `E3 REIMPLEMENTED` | Gates 7, 9 | A clean-room rerun, mutation of its guards, a false-claim run | Another instrument or source |
| `E4 REPLICATED` | Gate 8 | Independent data under the unchanged plan | A group outside the team |
| `E5 OUTSIDE_REPLICATED` | Gate 8, run by others | Replication by a group with no shared authors or code | Data outside its stated scope |

Rules for the ladder:

- Gates 11 and 12 apply at every grade.
- A grade drops when a later run fails. The failure stays on record next to the grade.
- A sealed run that passed its gates keeps its grade whatever the outcome. The record carries the grade together with the outcome (supported, narrowed, against, inconclusive), because a clean result against a claim is as well established as a clean result for it.
- Grade changes are an append-only history. Each entry names the ledger entry that caused it.
- `E4 REPLICATED` requires the plan unchanged and both implementations agreeing on the new data.
- A failed sealed run cannot be retried on the same sealed data. A revised plan needs new sealed data.
- Once the sealed part is opened, its outcome is not fed back into the plan. This is the `anchor` rule of section 2.2 applied to the verdict run.
- Novelty stays at `N0` until full-text prior work has been checked (Law 4, Gate 9). A "new" regularity in heavily studied public data is most likely known or an artefact.

## What each gate would have caught

Every row is a failure visible in public pull requests from the week of 2026-11-16.

| Failure | Gate |
|---|---|
| A frozen plan whose detector failed four of six known-answer tests, with false alarms up to 0.295 after a monotone map. Found before any data was opened. | 2 (it worked) |
| Gates that compare scores and ceilings declared by the submitter instead of measured ones (as of commit 0b60322, later commits changed some of this) | 3 (R7) |
| No public example yet | 4 |
| No public example yet | 5 |
| No public example yet | 5, 6 |
| A self-test whose pass flag was a constant, so it could not fail (as of commit 0b60322, later commits changed some of this) | 9 |
| Guard removals that left every test passing (13 sub-conditions in one review, 114 of 118 removals in another) (as of commit 0b60322, later commits changed some of this) | 9 |

## Changes after review

Items taken from the review of this pull request: the two cases of gate 4, the exchangeability and exact-arithmetic rules of gate 5, the tie and exit-code rules of gate 2, the source-lineage rule of gate 8, and the three ladder rules.

Two further proposals from that review are left to their authors as separate pull requests: binding each prose claim to its computed outcome, and a blinded verifier that receives only the claim, the pinned inputs and the code.

## What this proposal does not do

- It is text only. This pull request adds no certifier code and changes no existing file.
- It does not close the step from data to the world. It narrows that step to a stated bound and a record of what the claim has survived.
- The bound in gate 5 holds only under the stated assumptions (for example, that records are exchangeable under the null). Gates 6 and 8 test those assumptions. They do not prove them.

Gates 1, 3, 4, 5, 7, 8 and 10 need a certifier that recomputes from bytes, because each can be faked by a declaration. Gates 2, 6 and 9 can reuse the existing null and mutation tools once they run before data. Gates 11 and 12 need a small record check. Each certifier should come as its own small pull request, with its must-fail fixtures.
