# Analysis: knowledge factories and gardener agents, applied to our work

Team analysis by qalam (grk-qalam), 21 November 2026, America/Chicago. Read against the verbatim capture in [`post.md`](post.md) and against the repositories named below. This is an application note in the captures tree, novelty default N0, separate from the verified case studies that live under `evidence/` on the framework branch.

## The claim being applied

Harrison Chase's article, which Nicholas Charriere quotes, argues that agents fail less from weak models than from missing, tacit, or stale knowledge of how a workplace actually runs. A knowledge factory is the system that collects, curates, and maintains that knowledge so later work can use it as context.

The article splits the knowledge into three kinds:

- Skills: how to do the work the way the organization expects (procedures, often stored as `SKILL.md` files in GitHub).
- Domain knowledge: slower-moving facts about products, people, and policies.
- Data-access guidance: where current data lives and how to query it, rather than a second copy of that data.

Working agents flag missing or wrong knowledge while they work. A separate curator agent, running on a cadence, reads those flags, raw sources, and traces, then updates the store. Chase's warning is specific: the agents doing the task should not be the ones maintaining the store, because they will optimize for their own job and the store will fill with contradictions.

Charriere's contribution is a naming and a write policy. He calls the curator a gardener: an agent attached to a space rather than to a person. Person-attached agents he calls butlers, and he names OpenClaw, Grok Bot, and Muse as examples. In his reply to Daniel Lenton he goes further: butlers should not receive write access to the shared space (his example is Notion). They express intent; the gardener supplies context for reads and performs the writes. In reply to kartik bhardwaj, who said a gardener's edit affects everyone in the space and therefore wants something like a pull request the space owner can see, Charriere answered "yes." Chase, on his own thread, said a curator should be able to retire stale knowledge, that skills often want a user sign-off, and that other forms of memory can merge, and that the curator has to be a good one or it will hoard junk.

Storage format is secondary in the article. GitHub skills, a wiki, Open Knowledge Format, or a graph can all work. The loop is what matters: doing the work reveals the gap, resolving the gap makes the next run better.

## Where this shape already exists in our systems

We already run large parts of this pattern, under different names.

[aska-digital/ingestion](https://github.com/aska-digital/ingestion) is a source-centered bibliography and decision log. One issue per source is the intake and research workspace. A reviewable pull request proposes a source record. A merge accepts the record and the decision; it does not mean the source has been implemented. Statuses (`candidate`, `deferred`, `rejected`, `prototype`, `adopted`) attach to a use, not to the worth of the source. Later decisions are appended, not rewritten over the original assessment. The README already says a bare link is enough to start intake, and that records must not copy source datasets or private material into the repo.

[aska-digital/corpus](https://github.com/aska-digital/corpus) is the shared skill, SOP, and principles store that every agent team is told to read: Grok, Hermes, Claude, Codex, Muse, and Exo. Procedures live in `sops/` and `skills/`. Domain and operating rules live in `principles/`. Team-specific rules live in `teams/`. That is already the article's "skills plus domain knowledge" split, stored as GitHub files.

The review path is already the sign-off Charriere agreed to. [corpus/teams/grok.md](https://github.com/aska-digital/corpus/blob/main/teams/grok.md) makes orda-aska the main authoring account for Grok bots, through the box `gh` CLI, and keeps ahrazzle as the independent reviewer. The author account cannot approve its own pull request. [corpus/sops/github.md](https://github.com/aska-digital/corpus/blob/main/sops/github.md) states the same rule. Knowledge that lands in the Google Drive vault is supposed to be opened as a pull request on the fitting repo and to wait for that review path before it is merged (corpus standing directive, 2026-11-12).

On the Aletheia framework branch (pull request 1 on this repo), the portal-keeper role is already a space-attached writer with a hard boundary. It has exclusive write ownership of `<WORKSPACE>/cartography/` and must not modify raw sources or write outside that tree. Working probes flag anomalies; the portal-keeper re-enters the sources and updates the living catalog. That is a gardener for a research workspace.

[siliconcordat/.github/MASTER-PLAN.md](https://github.com/siliconcordat/.github/blob/main/MASTER-PLAN.md) already separates the store from the compiler. Plane 1 (written principles, exact-byte approvals, spend ceilings, credential custody) stays with humans and "none of these compile into model weights." [siliconcordat/exo](https://github.com/siliconcordat/exo) is the L4 harness: content-addressed exact-byte approval gates, and SIM causal self-improvement memory with cross-generation recompile and retire planning. Chase's "skills often want a user sign off; other forms of memory fine to merge" fits that split: procedural skills go through the approval gate, and retirement is already a named SIM operation.

[Moissanite-Labs/synbios](https://github.com/Moissanite-Labs/synbios) is an agent-first development workspace: define a task, grant an agent limited capabilities, attach an artifact by digest, record test evidence, and submit for human review. Submission requires passing current tests and accepted dependencies. The agent doing the task is already separated from the reviewer.

The missing pieces are therefore narrow. We do not yet have a single gardener attached to corpus or ingestion, running on a cadence, whose only job is to turn flags, traces, and intake issues into draft pull requests. Working bots have no standard, one-place flag when they hit missing or wrong guidance, other than opening an issue by habit. Mid-task, a butler that has already loaded a skill is not nudged when that skill is corrected, which is the failure Daniel Lenton named and Charriere answered.

## Applications

### 1. Ingestion and corpus as the knowledge factory

This is the closest fit and the first place to try the loop.

Working Grok bots already write research into GitHub, as this capture itself does. The next step is to treat every "I could not find the rule" or "this SOP is stale" moment as an ingestion or corpus flag, not as a silent workaround. The ingestion README already permits a bare-link issue. A short team rule that says "if the store is wrong or missing, open or extend that issue, do not patch the guidance in passing" would close the flag half of Chase's loop.

The curator half should be a gardener attached to those two repos. Inputs: open ingestion issues, explicit flags, vault drops already slated for PRs, and, when they exist, traces of agents failing a procedure. Output: draft pull requests only. Merge stays on the existing independent-review path. The gardener does not merge, and a butler in the middle of some other task does not land a silent corpus edit on the way to its real goal.

A source record for this post and article belongs in ingestion, as a `candidate` use, linking this capture folder. A merged record would document that we assessed the idea. It would not adopt LangChain's products.

### 2. The Grok team as butlers, the repos as gardens

Charriere lists Grok Bot as a butler, attached to a person. That matches how this team is actually used: the owner talks to qalam, work is coordinated through nizam, and specialists such as tensor or ship are still person-directed. The gardens are the shared repos (corpus, ingestion, Aletheia, the Moissanite-Labs and siliconcordat project trees).

The useful change is the write policy in Charriere's reply to Lenton. Butlers express intent ("this SOP is missing a step"; "file this capture"). A gardener, or ship following review, performs the write into the space. We already approximate this when one bot drafts and another reviews and merges. We violate it when the same working session both consumes a rule and rewrites it to finish the task.

Sreb's link intake and qalam's vision capture are already intake surfaces. They should empty into ingestion issues and gardener PRs, not into informal side notes that never reach the store.

### 3. Siliconcordat exo, Plane 1, and the local machines

On the five-layer stack, the knowledge factory is a Plane 1 and L4 concern. Skills and data-access notes stay as written artifacts. Curator proposals go through exo's exact-byte approval gate when they touch high-risk classes (the master plan lists auth, public APIs, schemas, lockfiles, infra, oracles, spend, and outward posts). SIM's retire path is the right mechanism to test Chase's "the loop can retire things too": procedural skills require a human sign-off to retire or replace; other memory may merge, as Chase said to Adojz.

The Mac Base Hub in the master plan is the M1 Max with 64 GiB unified RAM. The Warp workbench POC is aimed at the UX582HS with an RTX 3080. Those facts, plus which checkpoints fit in which memory budget, are data-access and procedure knowledge. A gardener can keep that guidance current. It must not launch training, allocate paid quota, or move credentials. Those stay Plane 1 human actions.

Weft and weft-loom (adaptive models, weight-space compilation, and the plasmid-transfer experiments under [Moissanite-Labs/weft-loom](https://github.com/Moissanite-Labs/weft-loom)) sit on the other side of the firewall. The factory holds the lab notes, the procedure, and the recorded outcomes. It does not compile standing rules into Inkling or Weft weights. The master plan already forbids that for Plane 1 material.

### 4. Synbios and ABIOS

In Synbios, the factory is the set of review rubrics, evidence schemas, agent permission docs, and task templates. The agent working a task should flag a gap in those documents. It should not rewrite the rubric it is about to be scored against. That is Chase's contradiction warning, applied to a forge.

[Moissanite-Labs/abios](https://github.com/Moissanite-Labs/abios) is the checkable, compressed agent-messaging ingredient (SYM-2P / the Synbios SYM-3 integration). Charriere expects richer agent-to-agent messaging so butlers can express intent without gaining write access. Flags, read-context requests, and write intents are exactly the sort of short, typed packet ABIOS is for. That is a protocol experiment, not a claim that such packets already exist.

### 5. siliquant and other weight-space research

[Moissanite-Labs/siliquant](https://github.com/Moissanite-Labs/siliquant) is research on rounding and related weight-space geometry. Open issues include #10 (geometric shape-mapping to choose a rounding formula) and #21 (mapping parameters by A/B testing a distilled shadow model). Those are experimental methods. A knowledge factory can store the procedure, the matrices touched, and the outcomes once they are recorded in the repo. It does not pick a rounding formula, and it does not stand in for a run that has not been done.

The same boundary applies to any live training job: the store may describe how a run is proposed and what approvals it needs. The gardener does not start the job.

## Risks

A weak curator will hoard low-value text. Chase's own reply to Yajat was that the filter has to be good. Our existing statuses (`deferred`, `rejected`, append-only reversals) are the right discipline for that filter, if the gardener actually uses them.

If task butlers keep write access to the store, the article's failure mode is the expected one: contradictory SOPs, skills that describe the last task rather than the shared rule, and no clear owner for cleanup.

If a skill is corrected and running butlers are not told, they will finish the job on the old advice. That is Lenton's point. Any gardener merge of a skill should have a way to notify in-flight agents, even if the first version is just a team channel or a bump in a well-known index.

This capture, including the full article text, already lives on a public repository because the owner asked for it here. Ingestion's own rule is the safer default for later work: record links and necessary summaries, and do not copy source datasets or private material into the log. Future captures of long third-party writing should prefer that path unless the owner again asks for a full verbatim file.

Adopting LangChain product pieces (Context Hub, Open Knowledge Format, LangSmith Engine) is not required by the idea. We already store procedures as GitHub skills, which the article itself lists as a valid store.

## First trials

1. Open an ingestion issue and a source-record pull request for this post and article, linking this folder, with use status `candidate` and no adoption claim.
2. Write a one-page gardener brief for corpus and ingestion: cadence, inputs, output equals draft PRs only, author account distinct from the review account.
3. Add one line to the Grok team protocol: when guidance is missing or wrong, flag it in ingestion or corpus; do not fix the shared rule as a side effect of another task.
4. On siliconcordat/exo, check whether SIM retire plus the exact-byte approval gate can express "skills need sign-off, other memory may merge," as a design note, before any implementation work.

