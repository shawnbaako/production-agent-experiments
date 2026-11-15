# 05 · One agent for chat and background work

**Question.** A production LLM agent did internal operations for a small consulting firm. It began
as a chat agent beside several separate background agents and fixed pipelines: a scheduled
attention pass, commitment help, a per-person background "watch", delegated specialists, a review
pass after runs, a decision-model step in front of the agent, and several ways for a run to continue
itself. From 2026-10-20 it was consolidated into one agent: chat and background became two ways of
starting the same agent, with one loop, one context and one set of permissions. What happened to
reliability, correctness, cost and complexity, and how much of it can be put down to the
consolidation?

**Status.** Case report from one private production system. The numbers come from that system's
records, its git history and its written evidence; none can be recomputed from this folder. Only
aggregates are given. The only like-for-like comparison is a 10-case outcome eval with one to three
runs per arm. Read it as an account of what happened, not as a result that generalises.

**Short version.**

- **Background work stopped duplicating itself.** Before the change, three agents with their own
  contexts acted on the same work: the chat agent, a per-person background agent and a firm-level
  agent. In one hour a partner's 25 edits to one email woke his background agent 15 times, and it
  opened four separate send approvals for that one email. Questions were asked twice and never
  withdrawn, and seven repeat guards had been stacked on top to hold it back. After the change, one
  agent per person runs every turn with the same context, so it sees what it is already doing.
- **Background model calls fell by about 85%, and background spend by about 85–90%.** In the week of
  2026-10-12 the background pipelines made 6,656 model calls for $51.64. After the consolidation,
  background turns made 658–1,187 calls a week for $5.34–$7.69. The price of a call barely moved
  ($0.0078 before, $0.0065–$0.0081 after), so the saving is in the number of runs, not in cheaper
  calls.
- **The agent became coherent where it had been fragmented.** On a 10-case outcome eval:
  - a stated preference about colleagues held in 3 of 3 runs, up from 1 of 3;
  - a reassignment arriving by mail was taken in 3 of 3, up from 0 of 3;
  - a direction given in chat became owned, ongoing work in 4 of 4 at the end, up from 0 of 3;
  - two mails on one matter produced one message.

  Tool searches per turn fell from 6.8–17.6 to 2.1–2.6, and the change removed about 48,000 lines of
  application code (about 40,000 net of what was added), about half the tools and all seven repeat
  guards.
- **What it did not do:**
  - It did not make each run cheaper. Spend per eval run rose from $0.71–$0.99 to $1.72, because a
    background turn now carries the person's conversation, and one person's work wakes the agents of
    colleagues it concerns.
  - The consolidation caused regressions, each lasting days to about a week. Found tools could not
    be called; one partner had no background help; a retry asked for the whole output budget.
  - Price routing, which cut the cost of each unattended call, started on 2026-10-14, before the
    consolidation.
  - The first phase of the change has no outcome eval; the 10-case eval measures only the second.

## Setting

- **The agent:** a tool-calling loop working for two partners and one staff member, in chat and in
  background runs. Production model: DeepSeek V4.1 Flash (a second variant for a "strong" setting),
  through OpenRouter.
- **Before 2026-10-20**, read from the source and production on that day:

  | Actor | What started it | What it could see | How it reached a person |
  |---|---|---|---|
  | Chat agent | A person's message | The conversation; ten board tasks | Its replies |
  | Per-person background agent | Changes in the person's work, schedules, driven tasks | Its own earlier runs and up to five earlier runs of the task; not the chat | Its own notices, questions and approvals |
  | Firm agent (attention pass, commitment help, and other pipelines) | Schedules and events, run as "the firm" | The request and a context built by its own code; no history, goal or task | Its own notices, questions and approvals |

  An investigation on 2026-09-28 had already found two separate planner loops in one service and
  11 domain pipelines, each with its own tool set of 3 to 19 entries.
- **After 2026-11-07:** every turn, whether a person wrote, their work changed or a time arrived,
  runs in that person's one conversation, with the same prompt, context, tools and permissions.
  Only that turn decides what reaches the person: a message, an item in a "needs you" list, or a
  push. Outside effects still stop at approval gates in every turn.

## Why

What production showed on 2026-10-19 and 10-20, from read-only queries:

- In 34 hours, background work put 66 items in front of one partner: 26 notices written into his
  chat, 30 items in his "needs you" list and 10 run replies. 13 arrived in his quiet hours.
- One partner spent 25 chat turns on one email. Each of his edits woke his background agent, which
  ran 15 times in that hour without the chat transcript and opened four separate send approvals for
  the same email. The firm agent sent its own messages about the same work.
- A background run asked the same question twice. When the partner told the chat agent not to stop
  and ask at every step, the chat agent did the work but did not answer or withdraw the run's
  questions.
- Repeated contact was held back by seven guards added one after another, each patching a
  symptom of the one before.

In the 30 days to 2026-10-21 the attention pass ran 891 times, made 7,363 model calls and cost
$32.79. It tried to ask 305 questions, and 266 of those were refused by its own guards. Of the 20
questions it did ask, people decided 15. It made 9 tasks and 83 notices; nothing records whether a
notice was read.

## The practice

1. **Delete what produced little, then fold what was left.** Phase one removed pipelines with
   little use (scheduled nurture, delivery review, client updates, portfolio review, the attention
   pass, commitment help, reply preparation, review passes, repeat guards). Each piece of value they
   delivered was handed to the owner's own agent, woken by the event.
2. **One context.** Background turns read the person's conversation, notes and pending items, the
   same as chat.
3. **One set of permissions.** The background-only grant, with its seven checkboxes and about
   1,900 lines of checks, was deleted. In 30 days it had refused 50 task updates that chat would have
   allowed. The approval gates on outside effects stayed.
4. **One list of what starts a turn,** shown to the person, with one lock per person so chat and
   background never run at once.
5. **One voice.** A turn speaks through its own messages. Pushes go only where the agent marks
   something to interrupt. Marking a task done stops its work.
6. **Each step measured on the same eval,** on a restored copy of production with the production
   models and the real scheduler. Mail entered as the records the mail ingest writes. A change was
   kept only if no case fell.

## Complexity

| Measure | Before | After | Source |
|---|---|---|---|
| Planner loops in the service | 2 | 1 | 2026-09-28 investigation; consolidation plan |
| Agents with their own context | 3 (chat, per-person background, firm) | 1 per person | Consolidation plan |
| Hub tools / loop built-ins / tools listed per turn | 272 / 22 / 22 | 125 / 10 / 20 | Plan status, 2026-10-20 (production counted with a Google catalogue added; the after figure without it) |
| Stacked repeat guards | 7 | 0 | Plan deletion list |
| Application code lines, phase one (one merge, 2026-10-21) | | +4,747 / −51,946; −40,992 excluding deleted test files | git, command below |
| Application code lines, steps 2–5 and follow-through | | +2,692 / −6,761 | git, command below |
| Non-test source lines (`.py`, `.ts`, `.tsx`, `.mjs`) | 261,221 (2026-10-20) | 209,712 (2026-11-07) | git, command below |

The line counts cover the service and web app source directories. The second-phase steps removed
3,805, 2,038, 516 and 280 lines and added 819, 1,255, 305 and 94; the follow-through added 219 and
removed 122. The fall in total source also includes other work merged in the same weeks, and a test
suite deleted the day before (study 02).

```
# per merge: git diff --shortstat <merge>^1 <merge> -- <service src> <web src>
# test lines inside it: git diff --numstat ... | grep -iE 'test|spec' | awk '{d+=$2} END {print d}'
# source lines at a commit: git ls-tree -r --name-only <rev> -- <service src> <web src> \
#   | grep -E '\.(py|ts|tsx|mjs)$' | grep -vE '\.test\.|\.spec\.|/tests?/' \
#   | while read f; do git cat-file -p <rev>:"$f"; done | wc -l
```

## Outcome eval, step by step

Ten cases, on restored production copies, judged on outcomes (what happened, what was asked, what
reached a person), never on wording or tool order. The baseline is the code of 2026-11-04: phase
one was already done, and the separate background agent and its permissions were still there.
Baseline and steps 1–2 ran three times each. Steps 3–5 ran once, against the stored result of the
step before. A case that fell was rerun twice more.

| Case and check | Baseline | Step 1 context | Step 2 permissions | Step 3 starts | Step 4 voice | Step 5 schema | Follow-through |
|---|---|---|---|---|---|---|---|
| A stated preference about colleagues holds | 1/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | pass |
| Reassignment arriving by mail is taken | 0/3 | 0/3 | 3/3 | 1/1 | 1/1 | 1/1 | pass |
| The new owner's agent sees the reassignment | 0/3 | 0/3 | 3/3 | 1/1 | 1/1 | 1/1 | pass |
| A direction given in chat becomes owned, ongoing work | 0/3 | 0/3 | 0/3 | 1/1 | 0/1, reruns 1/2 | 0/1 | 4/4 after two fixes |
| The morning check is listed where the person sees it | 0/3 | 0/3 | 0/3 | 1/1 | 1/1 | 1/1 | pass |
| A quiet day: no message, ask or push | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | pass |
| Mail needing a reply: prepared, nothing sent | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | 1/1 | pass |
| Two mails on one matter: one message | 3/3 * | 0/3 | 2/3 | 0/1 | 0/1, reruns 0/2 | 1/1 | 0/3, then 2/2 after a fix |
| A partner's rewrite of a draft is followed later | 0/3 | 0/3 | 0/3 | 0/1 | 0/1 | 0/1 | 0/3, then 2/2 with a changed check |
| A deferred "later" comes back when relevant | 0/3 | 0/3 | 0/3 | 0/1 | 0/1 | 0/1 | 1/2 with a new trigger |
| Tool searches per turn | 6.8–17.6 | 2.1–2.6 | 1.9–4.0 | 1.5 | 3.2 | 2.8 | |
| Repeated searches per run | 32, 32, 69 | 5, 5, 4 | 2, 4, 7 | 0 | 18 | 7 | |
| Failed tool calls per run | 14, 17, 32 | 5, 11, 8 | 18, 6, 14 | 6 | 15 | 8 | |
| Model spend per eval run | $0.71–$0.99 | $0.72–$1.03 | $1.26–$1.79 | $1.04 | $2.56 | $1.72 | |

\* The baseline passed this case only because the background agent's messages never reached the
person at all. Step 1 made them visible and the case started failing.

How to read the table:

- **Step 2's comparison arm was a separate step-1 run,** with 1.47–2.73 searches per turn and
  $0.84–$0.89 per run. A stored step-2 run had also passed the "direction" case 2 of 3. Results
  differ between arms of the same code; one run either way is noise.
- **The "direction" case passed at the end on a stricter check.** Before, a background turn that
  started counted. At the end, every background turn had to complete and move the work forward. It
  passed 4 of 4 only after two fixes. One stopped a task's first run being revoked when its own
  instructions were written. The other measured an image turn's text in tokens, not bytes.
- **The rewrite case passed only after its check was changed.** The restored copy held the agent's
  real note on the partner's email voice, built from his sent mail, and the case's invented rewrite
  contradicted it. The agent followed the real record.
- **Spend rose because more turns ran.** From step 2, a colleague's agent woke on what was handed
  to it. In step 4 one colleague turn cost $0.63 by itself, mostly searching for a client name that
  was invented and not on file.

## Duplicate and wasted background work

**What it looked like before.** From read-only queries on 2026-10-19 and 10-20, and the 30 days before:

| Symptom | Count |
|---|---|
| Background runs woken by one partner's edits to one email, in one hour | 15, without the chat transcript |
| Send approvals opened for that one email | 4 |
| Items put in front of one partner by background work in 34 hours | 66 (13 in quiet hours) |
| Attention-pass runs in 30 days | 891, making 7,363 model calls for $32.79 |
| Questions the attention pass tried to ask in those 30 days | 305, of which its own guards refused 266 |
| Repeat guards, each added to patch the one before | 7 |
| Overnight re-runs of the same research on 2026-10-14/15 | 7 |

Each of these is the same failure: an agent acting on work another agent was already doing, without
that agent's context. The guards treated the symptom; the consolidation removed the cause, because
every turn now reads the person's conversation, notes and pending items.

**Background model calls and spend, week by week.** "Pipelines" are the separate background agents
before the change (attention pass, commitment help, research, inbound mail, meeting synthesis).
"Background turns" are the consolidated agent's scheduled and event-started turns. Person-started
turns are left out of both columns.

| Week of | Background calls | Background spend | Spend per call | Where it ran |
|---|---|---|---|---|
| 10-12 | 6,656 | $51.64 | $0.0078 | Pipelines |
| 10-19 | transition | transition | | Pipelines deleted on 10-20/21 |
| 10-26 | 1,187 | $7.69 | $0.0065 | One agent |
| 11-02 | 953 | $6.22 | $0.0065 | One agent |
| 11-09 (to 11-13) | 658 | $5.34 | $0.0081 | One agent |

The week of 10-19 is left out: the pipelines ran for part of it and calls were not yet tied to turns.
In the week of 10-26, 899 further calls ($4.69) were not tied to any turn, and they are not counted
above; from 11-02 such calls were under 30 a week.

How much of this is the architecture:

- **The number of runs is.** The fall in background calls is the deleted pipelines and the wakes
  that no longer duplicate one another. A separate replay of 2026-10-20 without a model estimated
  the new wake rules alone would have started 44 runs instead of 63.
- **The price of a call mostly is not.** Price routing started on 2026-10-14, inside the 10-12 week,
  so that week's per-call figure is a blend. Per-call cost is about the same on both sides, which is
  why the saving is attributed to run count.
- **A person's own use is not part of this comparison.** Person turns fell over the same weeks for
  reasons unrelated to the architecture; they are excluded from the table above.

## Production, week by week

Read-only aggregates. "Person turns" are turns a person started and was waiting on. "Background
turns" are scheduled or event-driven. Weeks start on Monday; the last week has data to 2026-11-13.

| Week of | Model calls | Error replies | Billed cost | Turns (person / background) | Failed turns | Avg cost per turn | Median turn time | Avg input per call | Cached input | Calls per turn |
|---|---|---|---|---|---|---|---|---|---|---|
| 10-05 | 3,839 | 4.2% | ($3.13) | 204 (30 / 174) | 44 (22%) | — | 129 s | 42k | — | — |
| 10-12 | 8,952 | 8.4% | $68.31 | 381 (133 / 248) | 76 (20%) | ($0.195) | 241 s | 58k | — | — |
| 10-19 | 7,308 | 0.9% | $46.17 | 427 (76 / 351) | 16 (3.7%) | $0.094 | 93 s | 67k | 18% | — |
| 10-26 | 3,145 | 2.2% | $18.30 | 131 (56 / 75) | 7 (5.3%) | $0.142 | 176 s | 81k | 86% | 24.7 |
| 11-02 | 1,708 | 4.6% | $10.42 | 114 (68 / 46) | 2 (1.8%) | $0.094 | 83 s | 64k | 86% | 15.1 |
| 11-09 | 989 | 3.9% | $7.65 | 90 (35 / 55) | 1 (1.1%) | $0.085 | 78 s | 67k | 78% | 10.8 |

Gaps in the record:

- **Billed cost was recorded only from mid-October.** Earlier weeks show near-zero cost, which is
  not real, so they are left out or bracketed.
- **Turn spend was recorded from 2026-10-18.** The 10-12 figure covers one day.
- **Cache figures start in the week of 10-19,** and calls per turn in the week of 10-26.
- **The turn table does not hold every older pipeline run.** The attention pass ran as separate
  work items, so background turns before 2026-10-21 are undercounted. The call and cost columns
  include everything.

What the series shows, and what it does not:

- **Cost per call stayed about the same:** $0.0076 in the week of 10-12, $0.0058–$0.0077 after.
  Weekly cost fell because there were fewer calls. For background work that is the consolidation
  (previous section); person turns also fell, for unrelated reasons.
- **The cost cut came before the consolidation.** Daily cost was $34.82 on 10-14. It was $1.89 and
  $1.99 on 10-17 and 10-18, after unattended calls moved to the cheapest adequate host and the
  attention pass moved from a timer to events. It rose again to $23.65 on 10-19 (the day of the
  email case above) and $10.78 on 10-20. It was $1.53–$1.96 a day from 10-22. By caller, in the
  week of 10-12 the attention pass cost $28.45 and commitment help $12.92. After the deletion the
  shared loop carried all of it: $42.36 that week, $18.27 the next.
- **Prompts did not get smaller.** Average input per call went from 58k tokens to 64k–81k. Giving
  background turns the conversation was expected to add 8–10k tokens to their first call. The
  cached share rose to 78–86% after a separate change made the start of the prompt stable across
  turns.
- **Failed turns fell from about 20% to 1–5% a week.** Most earlier failures were turns stopping
  at their step limit (55 in the week of 10-12). Hitting the output limit on reasoning was the most
  common failure in the old pipelines: 460 of the attention pass's 473 failed calls in the week to
  10-18. The pipelines that produced those failures were deleted, but limits, retries and routing
  also changed in the same weeks.

## Regressions caused by the consolidation

| Regression | How long | Cause |
|---|---|---|
| The agent found tools it could not call, and looped on search: six turns made 36 to 133 searches, one searching the same exact name 124 times | 2026-10-21 to fixes on 10-27, 10-28 and 10-29 | To shrink prompts, tool-search results stopped carrying input schemas, on the assumption that found tools would join the tool list. Earlier turns' tools often filled the list's space first, so they never joined. The change had been measured on a replay (last prompt 376k to 267k bytes) and still shipped the defect |
| A retry after a cut-off reply asked for the whole output budget; one chat write reasoned through 131,072 tokens in 251 s without writing | 2026-10-21 to 10-22 | A fix for a worse defect: the old retry switched reasoning off and, twice on a copy, then said a meeting record had been saved when nothing was. The fix now doubles the room on each retry |
| Saving a contact address failed | About a day, 2026-10-21 to 10-22 09:30 | A change made while fixing consolidation proof findings wrote an explicit null into a non-null column. Not architectural |
| One partner had no background help | At least four days, from 2026-10-23 11:04 | His background agent was stored as a task on his board; marking the task done ended it. In the same period two partner calls got no meeting record, because the only reader of a landed transcript was the host's background agent, and the host had none |
| One chat edit woke several background runs: 4 runs and $0.97 for one plan edit; 7 runs for one call | Seen 2026-10-28 and 10-30; fixed 11-01 | The agent's own writes counted as news. A replay without a model estimated 1 and 3 wakes under the fix |

Still failing at the end:

- **A deferred "later" item** came back properly in only one of two runs.
- **Morning checks failed silently.** On 2026-11-05 and 11-10 they ended with an empty answer and
  nobody was told. In the 7 days to 11-11, 65 model replies (6% of reply calls) used up their
  whole reasoning budget.
- **Two analysis tasks** in a separate eval (market sizing, annual planning) failed 3 of 3 runs on
  figures and formulas. They are listed for completeness; nothing ties them to the architecture.

## What else changed at the same time

- **Price routing,** on 2026-10-14. Unattended calls went to the cheapest host above a throughput
  floor.
- **The attention pass moved from a timer to events** on 2026-10-17, before it was deleted.
- **A different stronger model setting** came into use on 2026-10-18.
- **The test suite was deleted** on 2026-10-20 (study 02).
- **Several product surfaces were retired** in the same week.
- **Changes beside the consolidation:**
  - prompt-size fixes from 2026-10-27: a fixed result cap, history capped at 32 KB, a stable
    prompt start;
  - tool-search fixes;
  - a fix for tool-call text leaking into replies.
- **Person use fell,** from 133 person turns a week to 35, for reasons unrelated to the
  architecture. It does not enter the background comparison. One partner was without background
  turns for some days (a regression, listed above).
- **The eval itself changed.** Its harness, triggers and two pass checks were revised during the
  steps.

## What this does not show

- **The first phase's effect on outcomes.** No eval ran the pre-2026-10-20 system. Evidence for
  that phase is limited to:
  - 30-day usage reads of what the deleted pipelines produced;
  - booking replays on a copy;
  - a replay without a model of 2026-10-20, in which the new wake rules would have started 44
    runs instead of 63 and spent $3.91 instead of $5.98. That is an estimate from recorded spend,
    not a run.
- **Whether the person was interrupted less.** The plan set a per-person attention report with a
  baseline of 2026-10-14 to 10-20. No result of it was found.
- **Repeatability.** Steps 3 to 5 ran once each. Three runs a side could not separate 0/3 from 1/3.
- **Other systems.** One firm, three users, one model family, one month.
- **Human judges.** The eval's judge is a model, and the cases were written by agents from the
  design intent.
- **Usefulness of background work in production.** On a copy, mail-started and morning turns ran
  and produced work. Whether that work was useful each day was not measured.

## Reading

1. Many of the failures before 2026-10-20 came from separate agents acting without each other's
   context. Background work that never saw the chat, duplicate approvals, and questions nobody
   withdrew were all of that kind. The cases built to catch those failures passed after the
   consolidation, and most passed on the step written for them.
2. The consolidation removed most background work by removing the duplication behind it:
   background calls fell from 6,656 a week to under 1,200, at about the same price per call. It did
   not make an individual run cheaper. Per eval run it cost more, because each turn carries the
   person's context and one person's work now wakes the agents of the colleagues it concerns. The
   cheaper price of each unattended call came from routing, which started first.
3. Removing structure created its own defects, for about a week each. Proofs on a restored copy
   caught some before merge (a false "record saved" claim, a migration that failed on an empty
   database) and missed others (the schema removal).

## Related work

**Single agent or several**

- Schluntz and Zhang (Anthropic), "Building effective agents", 2024-12-19.
  https://www.anthropic.com/engineering/building-effective-agents. Workflows (fixed code paths) suit
  well-defined tasks; agents suit open-ended ones; start with the simplest solution. The pipelines
  deleted here were workflows built for tasks that turned out not to be well-defined, and 30 days
  of use showed little value from them. This case agrees.
- Yan (Cognition), "Don't Build Multi-Agents", 2025-06-12.
  https://cognition.com/blog/dont-build-multi-agents. "Share context" and "actions carry implicit
  decisions". The email case above (four approvals and two agents messaging about one email) is
  what it predicts. This case agrees.
- Hadfield et al. (Anthropic), "How we built our multi-agent research system", 2025-06-13.
  https://www.anthropic.com/engineering/multi-agent-research-system. The multi-agent system did
  better on broad research, at about 15 times the tokens of chat, and is a poor fit where agents
  must share context or depend on each other heavily. Operations work for one person is that poor
  fit. This case does not test the research setting it recommends. Research here was also folded
  into the main loop, and its quality was not measured against the old separate runtime.
- Sarkis (Anthropic), "Building agents: When to fold subagents into your main agent loop",
  2026-10-22.
  https://claude.com/blog/building-agents-when-to-fold-subagents-into-your-main-agent-loop. One
  loop with tools found as needed; keep subagents only where context bloat, parallel work or
  conflicting instructions measurably need them; build an end-to-end eval first; fold in one
  piece at a time; run each task more than once. The second phase followed this, except that
  steps 3 to 5 ran each case once.
- Cemri et al., "Why Do Multi-Agent LLM Systems Fail?", 2025. https://arxiv.org/abs/2503.13657.
  14 failure modes in three groups (system design, misalignment between agents, task
  verification), from over 1,600 traces. The failures before consolidation fit its middle group
  (agents ignoring each other's state and repeating work). This case's later failures (silent
  empty answers, retry budgets) are of a single agent and fall outside it.
- Gao et al., "Single-agent or Multi-agent Systems? Why Not Both?", 2025.
  https://arxiv.org/abs/2505.18286. The advantage of multi-agent systems shrinks as models
  improve. Not tested here.
- Tran and Kiela, "Single-Agent LLMs Outperform Multi-Agent Systems on Multi-Hop Reasoning Under
  Equal Thinking Token Budgets", 2026. https://arxiv.org/abs/2604.02460. Many reported
  multi-agent gains come from uncounted compute. Consistent with this case's spend not falling: one
  agent did not mean less compute.
- Kim et al., "Towards a Science of Scaling Agent Systems", 2025.
  https://arxiv.org/abs/2512.08296. Multi-agent overhead hurts tool-heavy tasks, and results range
  from +80.8% to −70.0% against a single agent depending on the task. Operations work here is
  tool-heavy and sequential. This case is consistent with it, but it is not a controlled test.

**Context**

- Hong, Troynikov, Huber (Chroma), "Context Rot: How Increasing Input Tokens Impacts LLM
  Performance", 2025-07-14. https://www.trychroma.com/research/context-rot. Performance falls as
  input grows, even on simple tasks. This is the cost side of one context. Prompts grew to 64k–81k
  tokens on average. A separate production measurement (2026-10-28 to 11-01) found replies that
  were all reasoning in 0.3% of calls under 50k tokens and 6.7% above 150k. Folding everything
  into one context makes this the main remaining failure, and the case does not contradict the
  report.
- Rajasekaran et al. (Anthropic), "Effective context engineering for AI agents", 2025-09-29.
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents. Context is a
  finite resource; compaction suits long conversations; subagents with clean windows suit parallel
  research. This system took neither route. It capped history at 32 KB and kept older turns
  searchable.

**Agents started by events, and background beside chat**

- Chase (LangChain), "Introducing ambient agents", 2025-01-14.
  https://www.langchain.com/blog/introducing-ambient-agents. Agents that act on an event stream,
  with three ways to involve a person: notify, question, review. This system arrived at the same
  three (a message, an item in a "needs you" list, an approval gate). The difference is that here
  the event-started turn is the chat agent itself, not a separate one.
- Garimella (Actively), "Human-agent collaboration for long-running agents", byline 2025-10-31.
  https://www.actively.ai/blog/human-agent-collaboration. The opposite design: a long-running
  background agent per account, and short-lived chat agents with read-write access to its
  memory. This system's middle state looked similar. Background turns ran in the person's
  conversation but were filtered out of each other's view, and it failed. That shows a filtered
  shared store failing, not that a shared-memory design fails.
