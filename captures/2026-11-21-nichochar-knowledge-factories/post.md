# Capture: Nicholas Charriere on knowledge factories and gardener agents

A verbatim record of a public X post, the post it quotes, the X article attached to that quoted post, the author's own replies, and the quoted author's replies. Copyright remains with the original authors. Canonical URLs are listed in each section.

## Retrieval

| Field | Value |
| --- | --- |
| Retrieved at | Saturday, 21 November 2026, 4:38 PM CT (America/Chicago) |
| Method | X public read API (`get_posts_by_id`, `get_posts_by_ids`, `search_posts_all`) |
| Post ID | `2124182843102535974` |
| URL | https://x.com/nichochar/status/2124182843102535974 |
| Conversation ID | `2124182843102535974` (this post opens the conversation) |
| Language | `en` |
| Reply settings | everyone |

Self-thread search: `conversation_id:2124182843102535974 (from:nichochar OR from:hwchase17)`. Quoted-author thread search: `conversation_id:2124181216719151585 (from:hwchase17 OR from:nichochar)`. Both were paged until an empty page.

Public metrics below are a snapshot at retrieval and will change.

## Author

| Field | Value |
| --- | --- |
| Name | Nicholas Charriere |
| Username | nichochar |
| User ID | `234698931` |
| Profile | https://x.com/nichochar |
| Bio | i like legos and exponentials / ai products @notionHQ / prev @get_mocha (YC S23) @cruise @pinterest |
| Location | San francisco |
| Account created | 6 January 2011, 4:11:57 AM CT (America/Chicago) |
| Verified | yes (blue) |
| Protected | no |
| Followers / following (snapshot) | 8,684 / 1,832 |
| Posts / likes (snapshot) | 13,652 / 18,903 |

## Post text (canonical long form, `note_tweet`)

The API returned the full text in `note_tweet`. A trailing space after the period in the second paragraph is present in that field and is preserved here.

```
I suspect we will start hearing about "Knowledge Factories" a lot in the coming months.

I'm particularly interested in what Harrison calls the "curator agent". 

I call these gardeners: agents that are attached to a space, rather than a person (I call those ones butlers, like OpenClaw, Grok Bot or Muse).
```

## Timeline display text (`text`)

The same body through `like`, after which the image and quoted-post t.co links are appended and the remainder of the sentence (`OpenClaw, Grok Bot or Muse).`) is carried only in `note_tweet`. `display_text_range` is `[0, 277]`.

```
I suspect we will start hearing about "Knowledge Factories" a lot in the coming months.

I'm particularly interested in what Harrison calls the "curator agent". 

I call these gardeners: agents that are attached to a space, rather than a person (I call those ones butlers, like https://t.co/OG6uPl1opJ https://t.co/S9irZ2wWs3
```

## Public metrics (snapshot at retrieval)

| Metric | Count |
| --- | ---: |
| Impressions | 72,241 |
| Likes | 797 |
| Reposts | 41 |
| Replies | 32 |
| Quotes | 8 |
| Bookmarks | 1,581 |

Posted Saturday, 21 November 2026, 10:47:09 AM CT (America/Chicago). Source timestamp: `2026-11-21T16:47:09.000Z`.

## Attached media

One photo, no alt text in the API.

| Field | Value |
| --- | --- |
| Media key | `3_2124182604190760960` |
| Type | photo (PNG) |
| Pixels | 1170 × 848 |
| Source URL | https://pbs.twimg.com/media/HXqc0vjawAAal4F.png |
| Post media page | https://x.com/nichochar/status/2124182843102535974/photo/1 |
| Local copy | [media/nichochar-2124182843102535974.png](media/nichochar-2124182843102535974.png) |

The image is a black-background screenshot of the "curator agent" paragraph from the quoted article (white body text). The phrases "on some cadence" and "agent traces" are underlined. The wording matches that paragraph in the article text below.

## Quoted post

| Field | Value |
| --- | --- |
| Post ID | `2124181216719151585` |
| URL | https://x.com/hwchase17/status/2124181216719151585 |
| Conversation ID | `2124181216719151585` |
| Posted | Saturday, 21 November 2026, 10:40:42 AM CT (America/Chicago) |
| Source timestamp | `2026-11-21T16:40:42.000Z` |
| Author | Harrison Chase (hwchase17), user ID `2728439146` |
| Profile | https://x.com/hwchase17 |
| Bio (snapshot) | @LangChain / Always hiring: https://t.co/D5Ut3loFO7 |
| Account created | 29 July 2014, 2:22:50 PM CT (America/Chicago) |
| Verified | yes (blue) |
| Followers / following (snapshot) | 141,562 / 604 |
| Posts / likes (snapshot) | 18,025 / 17,301 |

The API `text` field HTML-escaped the ampersand as `&amp;`. The block below is the on-site form, with `&`.

```
all our agents at langchain (internal GTM & content agents, LangSmith Engine) have a learning loop with similar pieces

wrote about what we think makes up a "knowledge factory" https://t.co/xaAZb5i79q
```

### Quoted post metrics (snapshot at retrieval)

| Metric | Count |
| --- | ---: |
| Impressions | 145,842 |
| Likes | 1,098 |
| Reposts | 96 |
| Replies | 101 |
| Quotes | 39 |
| Bookmarks | 2,982 |

The t.co link `https://t.co/xaAZb5i79q` expands to the X article `https://x.com/i/article/2124180107669766144`. The API marked that expansion with HTTP status 404 on `unwound_url`. The article body was still returned on the post as `article.plain_text` and is captured from that field.

## Quoted X article

| Field | Value |
| --- | --- |
| Title | How to build a knowledge factory |
| Article ID | `2124180107669766144` |
| URL | https://x.com/i/article/2124180107669766144 |
| Author | Harrison Chase (hwchase17) |
| `plain_text` length | 8,211 characters |

The `plain_text` field uses typographic apostrophes (U+2019), curly quotation marks (U+201C / U+201D), em dashes (U+2014), hyphen-minus dashes in ` - ` breaks, and three narrow no-break spaces (U+00A0) after the "Skills.", "Domain knowledge.", and "Data access guidance." labels in the "pieces of knowledge" list. Those characters are preserved in the block below.

```
In order to make AI work for your company, the missing bit is not better models, it’s not just more context - it’s better knowledge. It’s knowledge of how your company works, what standards for operating you have in place, where data is stored and how it’s accessed.
Your most efficient employees have this knowledge in their head. They know who to talk to, where to go to answer questions, why you do things in a particular way. That knowledge is often tacit, implicit, scattered - sometimes present only in their head, sometimes scattered across a variety of documents.
In order to make AI work for your company, you need to collect, curate, and maintain a representation of that knowledge to pass to agents. The system that helps you do that is what we’re calling a knowledge factory.
We’ve built this at LangChain in a few ways. Our internal GTM and content studio agents are powered by a knowledge factory. LangSmith Engine (our agent that runs over traces and suggests fixes) maintains a knowledge factory per agent as well. This blog shares our learnings.
Context vs knowledge
Context is what an agent has available when doing a task.
Knowledge is the reusable understanding we maintain so it can do that task correctly: what a metric means, which source to trust, or how we handle a particular situation. Sometimes written down, often not.
A knowledge factory turns scattered documents and experience into knowledge that can become context for future work.
So knowledge is a form of context that the agent will get, but it’s often not (and shouldn’t be) the only context the agent gets. Other types of context you already ingest/store reliably, and that can just be provided directly to the agent (see the section on quickly changing data below).
From Software Factory to Knowledge Factory
The idea of software factories has risen sharply over the past year and a half. The idea is that rather than having your best engineers actually build software, they should build the factory (the systems) to help everyone at the company build software more efficiently. The actual building of the software can be done by agents.
General knowledge work is now following a similar path. Agents are good enough to make presentations, launch videos, do outbound. You should be leveraging them as much as possible for those tasks. But in order for them to accomplish those tasks they need all that tacit, implicit, scattered knowledge.
That is where you should devote resources. You need to build that knowledge, and more importantly a factory to collect, curate and maintain that knowledge. That is what will let you outsource more general knowledge tasks to agents.
The pieces of knowledge
There are generally a few pieces of knowledge you want to maintain.
How to do the work — Skills. Procedures, instructions, and scripts for accomplishing tasks the way your company expects.
How the business works — Domain knowledge. Definitions, policies, and facts about your products, customers, competitors, and organization.
Where to get current information — Data access guidance. Which sources to use, what data lives where, and how to query it.
 
Skills: these are procedures for how to do things “properly” inside your company. Instructions, scripts, for how to accomplish tasks in the particular way that your company requires. Often times, these were never written down before (instead passed coworker to coworker). You should strive to write them down.
Domain knowledge: this is knowledge that does not go stale frequently. It is often core information about people, products, competitors. This is often information that was written down - but was usually incomplete (or incorrect) just due to the sheer amount of knowledge here.
Data access guidance: You should have a good data strategy (Snowflake, Databricks, etc). That’s the foundation of useful agents. If the source of truth of data is there already, and it’s complete and up to date - there’s no need to maintain a separate copy. Rather, the new thing you’ll want to maintain is clear instructions on what data lives where and how to query it.
The pieces of the factory
All of this information is needed for useful agents. Don’t try to maintain it manually - that’s a herculean effort. Rather, you will want to create a system for maintaining it. Generally, the pieces look like:
 
A way for agents to flag missing knowledge: One of the best ways to learn what pieces of knowledge are missing is to have agents flag it as they are working. If they are asked to do something, and can’t find information, or find information that they discover is wrong - they should flag it! Give the agent a tool to at a minimum report what is wrong, and optionally suggest the correct update.
The curator agent: an agent to update, curate, and maintain this knowledge: This knowledge should not be kept up to date manually - too much work. And it should not be kept up to date solely by the agents that use it - they are great at flagging what’s wrong or missing, but fixing it requires deep understanding of the underlying knowledge and other sources of data. Asking agents - who are mainly trying to accomplish their own goals - to properly update and maintain this knowledge will cause it to become unruly and full of contradictions. Rather - you will want a curator agent that runs in the background, on some cadence, to update this knowledge. It should have access to all the raw sources of data (Notion, Slack, etc) where this knowledge may be scattered. It should have access to agent traces, so it can see how people are trying to use agents and codify that into skills. It should have access to the things that agents have flagged as wrong (the above section).
Storage for the knowledge: In some ways, this is actually the least important thing. You can store this knowledge in skill format in GitHub. In a single file in Notion. In OKF format in LangSmith Context Hub. In a knowledge graph in Neo4j. The curator agent should know how to interact with all of these formats (not that hard). In other ways, this is the least explored area. How do you represent memory? As an industry, we’ve converged on skills for “procedural memory”. For more semantic memory, a different standard will likely emerge (OKF?). It is early and no standard has yet emerged - so it’s probably best to not be too prescriptive or overly complicate what this format should look like.
Putting it all together
Let’s finish with an end to end example of an agent preparing a revenue report.
There’s base context the agent will need: the raw revenue numbers, stored in BigQuery and Salesforce.
Then there’s knowledge. It may consist of a few different types:
Skills: how to create reports in LangChain style. These are stored in GitHub in the standard skills format.
Long duration knowledge: the way we calculate ARR. This is stored in a company wiki.
How to access quickly changing knowledge: how to access that raw data in BigQuery/Salesforce. These are also just stored as skills, but this time in Context Hub.
The agent runs. Maybe it notices that we renamed a column in BigQuery. It figures out the correct column on the fly. It uses its tool it has to report issues to flag this, and suggest the proper column name.
After it creates the report, our finance lead works synchronously with the agent to fix a few formatting issues, including telling it to use a new header we now need to use for all LangChain documents.
That night, the curator agent sees the flagged issue. It also inspects the traces of the agent and notices this back and forth with our finance lead. It updates the relevant skills accordingly (to use the new column when fetching data, and to use the new header when drafting report).
 
Conclusion
The goal isn’t to document everything before agents can start working. It’s to build a system where doing the work reveals what knowledge is missing, and resolving those gaps makes future work better. Start with one recurring workflow, inspect where agents struggle, and close that loop.
We’ve built this at LangChain, and are working with a few customers to bring this to their agents (internal and external). If you’re interested in this - please reach out, we can help!
```

### Article figures

Cover plus three diagrams, no alt text in the API. Local copies are under `media/`.

1. Cover, 3840 × 1536, media key `3_2124180252293574656`, https://pbs.twimg.com/media/HXqar2DbsAAs_XI.jpg, [article-cover-HXqar2DbsAAs_XI.jpg](media/article-cover-HXqar2DbsAAs_XI.jpg). Title "How to Build a Knowledge Factory" over a LangChain logo and a press illustration that outputs a stack labelled `SKILL.md`.
2. "Pieces of knowledge," 2400 × 1200, media key `3_2124180329934315520`, https://pbs.twimg.com/media/HXqawXSbYAABTuC.jpg, [article-1-HXqawXSbYAABTuC.jpg](media/article-1-HXqawXSbYAABTuC.jpg). Three columns: Skills / How to do the work / `SKILL.md` / "Reports in LangChain style" / GitHub; Domain knowledge / How the business works / Wiki page / "How we calculate ARR" / Company wiki; Data access guidance / Where to get current information / Query guide / "Revenue: BigQuery and Salesforce" / Context Hub.
3. Factory loop, 2400 × 1200, media key `3_2124180380853149696`, https://pbs.twimg.com/media/HXqazU-bIAAhZzt.jpg, [article-2-HXqazU-bIAAhZzt.jpg](media/article-2-HXqazU-bIAAhZzt.jpg). "Agents doing work" send "Flags / Missing or wrong knowledge" and "Agent traces" into a "Curator agent / Runs in the background on a cadence," which also reads "Raw sources / Notion and Slack," then "Updates" a "Knowledge store" (Skills, Domain knowledge, Data access guidance) that returns to the agents "As context."
4. Revenue-report example, 2400 × 1200, media key `3_2124180451552342016`, https://pbs.twimg.com/media/HXqa3cWbMAAyfJO.jpg, [article-3-HXqa3cWbMAAyfJO.jpg](media/article-3-HXqa3cWbMAAyfJO.jpg). Four stages: Agent run / Revenue report (BigQuery renamed column, flag with a suggested fix) → Finance lead / After the report (request: new header for all LangChain documents) → Curator agent / That night (reads the agent flag and the trace with the finance lead) → Two skills updated (data fetching / new column; report drafting / new header).

### URLs attached to the article body

These appear as hyperlinks in the X article. They are not spelled out inside `article.plain_text`. Order is the order returned by the API.

1. https://docs.langchain.com/oss/python/deepagents/skills
2. https://www.langchain.com/blog/how-to-give-your-agent-memory
3. https://github.com/open-knowledge-format/open-knowledge-format
4. https://www.langchain.com/blog/components-building-company-harness
5. https://www.langchain.com/blog/introducing-context-hub
6. https://docs.langchain.com/langsmith/python/managed-deep-agents-schedules
7. https://www.langchain.com/blog/how-we-built-langchains-gtm-agent
8. https://www.langchain.com/contact-sales
9. https://www.langchain.com/blog/context-engineering-for-agents
10. https://www.langchain.com/blog/design-agent
11. https://www.langchain.com/langsmith/observability
12. https://www.langchain.com/langsmith/engine

## Author replies in this conversation (oldest first)

Replies by nichochar under `conversation_id:2124182843102535974`. Each parent is included so the reply can be read in context. Long-form replies use `note_tweet` when the API provided one.

### 1. Saturday, 21 November 2026, 11:18:29 AM CT

- URL: https://x.com/nichochar/status/2124190726489800906
- Post ID: `2124190726489800906`
- Metrics: 336 impressions, 0 likes, 0 replies, 0 reposts, 0 bookmarks

Parent, kartik bhardwaj (kartikb753), 10:50:07 AM CT, https://x.com/kartikb753/status/2124183590120657090:

```
@nichochar Gardener is a good name because it raises a question butlers don't have, which is who signs off. A butler answers to one person, but a gardener's edits change things for everyone in the space, so it probably wants something like a PR the space owner can see.
```

Reply:

```
@kartikb753 yes
```

### 2. Saturday, 21 November 2026, 12:00:17 PM CT

- URL: https://x.com/nichochar/status/2124201247368708594
- Post ID: `2124201247368708594`
- Metrics: 319 impressions, 2 likes, 1 reply, 0 reposts, 0 bookmarks
- Canonical text from `note_tweet` (the timeline `text` field cuts off after "express intent to")

Parent, Daniel Lenton (DanielLenton1), 11:50:53 AM CT, https://x.com/DanielLenton1/status/2124198882414625176:

```
@nichochar I'd want the gardener to nudge the butlers when a page they're already using gets corrected. Otherwise they can finish the task with the old advice.
```

Reply:

```
yep, over time i suspect we will get much richer agent-to-agent messaging mechanisms

once we do, butlers will not come into the garden and make changes themselves (you won't give write access to any agent into your Notion for example)

rather, they will express intent to gardeners who will provide the right context for read requests and will perform the writes for a given intent
```

The timeline display prefixes the same body with `@DanielLenton1 `.

### 3. Saturday, 21 November 2026, 3:13:46 PM CT

- URL: https://x.com/nichochar/status/2124249937588420815
- Post ID: `2124249937588420815`
- Metrics: 120 impressions, 0 likes, 0 replies, 0 reposts, 0 bookmarks

Parent, Atif Saleem (malikatifsaleem), 3:11:03 PM CT, https://x.com/malikatifsaleem/status/2124249253644239190:

```
@nichochar I have agents like mcc-intent, mcc-function, mcc-context (can rename as mcc-curate 🤔), mcc-vision, mcc-create and so on. These are small models fine-tuned for their roles in assisting the main agentic reasoning + multimodal mcc-stylist agent. Cost and latency were main factors.
```

Reply:

```
@malikatifsaleem very interesting. Does it work well? 

exploring similar ideas and looking for info around people who have tried
```

## Quoted-author replies on the quoted post (oldest first)

Replies by Harrison Chase under `conversation_id:2124181216719151585`. He did not reply in the nichochar conversation (the first search returned no hwchase17 posts there). Parent posts are included for context. Typographical slips in the source are left as returned.

### 1. Saturday, 21 November 2026, 10:45:34 AM CT

- URL: https://x.com/hwchase17/status/2124182445142757665
- Post ID: `2124182445142757665`
- Metrics: 1,299 impressions, 3 likes, 1 reply, 0 reposts, 1 bookmark

Parent, Adan Zweig (Adojz), 10:44:18 AM CT, https://x.com/Adojz/status/2124182126371487986:

```
@hwchase17 who decides when a piece of knowledge goes stale? curious if the loop can retire things too, not just add them
```

Reply:

```
@Adojz yup, the curator should be able to do tht
```

### 2. Saturday, 21 November 2026, 11:10:26 AM CT

- URL: https://x.com/hwchase17/status/2124188701563695195
- Post ID: `2124188701563695195`
- Metrics: 124 impressions, 1 like, 0 replies, 0 reposts, 0 bookmarks

Parent, Adan Zweig (Adojz), 10:56:21 AM CT, https://x.com/Adojz/status/2124185154776359064:

```
@hwchase17 nice. does the curator retire stuff on its own or does a human sign off on deletes?
```

Reply:

```
@Adojz Could be either! We see skills often want a user sign off. Other forms of memory fine to merge
```

### 3. Saturday, 21 November 2026, 11:56:00 AM CT

- URL: https://x.com/hwchase17/status/2124200169164120489
- Post ID: `2124200169164120489`
- Metrics: 2,200 impressions, 5 likes, 2 replies, 0 reposts, 0 bookmarks

Parent, Yajat (yajat_ai), 11:53:42 AM CT, https://x.com/yajat_ai/status/2124199590949978404:

```
@hwchase17 how do you figure out which knowledge is actually worth keeping? wouldn't the curator eventually end up collecting a lot of unnecessary stuff too?
```

Reply:

```
@yajat_ai Needs to be a good curator!
```

### 4. Saturday, 21 November 2026, 2:50:30 PM CT

- URL: https://x.com/hwchase17/status/2124244083409645866
- Post ID: `2124244083409645866`
- Metrics: 705 impressions, 1 like, 0 replies, 0 reposts, 0 bookmarks

Parent, Daniel Zambrini (DanielZambrini), 2:40:06 PM CT, https://x.com/DanielZambrini/status/2124241463584370768:

```
@hwchase17 Knowledge factory is a great name!!
```

Reply:

```
@DanielZambrini Was all @j_schottenstein
```

## Capture notes

- Third-party replies that neither author answered are left out, except for the parent posts above.
- Reply metrics are from the `get_posts_by_ids` / `search_posts_all` calls around the same retrieval window as the main snapshot, and may differ by a few minutes from the 4:38 PM CT main-post snapshot.
- The original post's first fetch, a few minutes earlier, already fell after the one-hour edit window (window ended 11:47 AM CT). The text here is the text returned at 4:38 PM CT.
- Article figure files were downloaded from the `pbs.twimg.com` URLs with `name=orig`.
