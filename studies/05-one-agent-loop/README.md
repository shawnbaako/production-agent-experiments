# 05 · One agent loop: why we replaced sub-agents and specialised background agents

**Our position.** A production agent that works for people, in chat and in the background, should be
one agent: one loop, one context, one set of permissions, started by whatever happens. Chat and
background are two ways of starting the same agent, not two agents. Specialised agents, sub-agents and
fixed pipelines beside the main loop each decide part of the work without the rest of the picture, and
the system spends its time and money reconciling them.

We built the other way first, ran it in production, and then consolidated. This is what we saw, what we
built instead, and what changed.

## What fragmentation looked like

Before the change the system had three kinds of agent, each with its own context:

| Agent | Started by | What it could see | How it reached the person |
|---|---|---|---|
| Chat agent | A message | The conversation | Its replies |
| Per-person background agent | Changes in the person's work, schedules | Its own earlier runs; not the chat | Its own notices, questions and approvals |
| Specialised pipelines (an attention pass, commitment help, research, inbound mail, meeting synthesis) | Timers and events | A context their own code assembled; no history or goal | Their own notices, questions and approvals |

Two planner loops ran in one service, beside eleven domain pipelines with their own tool sets of 3 to
19 tools. Every one of them was reasonable on its own. Together they produced this:

| What happened | Count |
|---|---|
| Background runs woken by one person's edits to one email, in one hour | 15, none of which saw the chat |
| Separate send approvals opened for that one email | 4 |
| Items background work put in front of one person in 34 hours | 66, 13 of them in quiet hours |
| Questions one pipeline tried to ask in 30 days | 305, of which its own guards refused 266 |
| Runs of that pipeline in 30 days | 891, making 7,363 model calls |
| The same research re-run overnight | 7 times |
| Repeat guards, each added to patch the one before | 7 |

Every row is one failure: an agent acting on work another agent was already doing, without that
agent's context. Questions were asked twice and never withdrawn when the person answered them in chat.
A preference stated in chat never reached the background. Reassignments arriving by mail were seen by
one agent and not the one that owned the work.

The usual response is guards: a repeat check, a dedupe rule, a cooldown, a review pass. We had seven,
and they made it worse. Each guard is another fixed decision made without context, and each one
patches a symptom of the split rather than the split.

## What we built

1. **One loop.** Every turn runs the same agent loop with the same prompt, tools and model, whether a
   person wrote, their work changed or a time arrived.
2. **One context.** A background turn reads the person's conversation, notes and pending items, the
   same as a chat turn. It sees what it is already doing.
3. **One set of permissions.** A separate background permission system (seven switches and about 1,900
   lines of checks) was deleted; in 30 days it had refused 50 updates the chat agent was allowed to
   make. The approval gates on outside effects, such as sending mail, stayed.
4. **Events start turns.** One list of what starts a turn, visible to the person, and one lock per
   person so chat and background never run at once. No timers that wake the model when nothing changed.
5. **One voice.** Only the turn decides what reaches the person: a message, an item in a "needs you"
   list, or an approval. Marking work done stops its background work.
6. **Delete before you fold.** Pipelines that produced little were deleted outright. What value they
   had moved to the person's own agent, woken by the event.

We did it in two phases: first deleting the specialised pipelines, then folding the remaining
background agent into the chat agent in five steps, each measured on the same outcome eval before the
next.

## What changed

### Background work stopped duplicating itself

Background model calls and spend per week. Before: the specialised pipelines. After: the one agent's
event-started turns. Person-started turns are excluded from both.

| Week | Background calls | Background spend | Spend per call |
|---|---|---|---|
| Before | 6,656 | $51.64 | $0.0078 |
| After, week 1 | 1,187 | $7.69 | $0.0065 |
| After, week 2 | 953 | $6.22 | $0.0065 |
| After, week 3 (5 days) | 658 | $5.34 | $0.0081 |

About 85% fewer background calls and 85–90% less background spend. The price of a call barely moved,
so the saving is in the number of runs: work that no longer happens twice, and pipelines that no longer
run on a timer.

### The agent became coherent

A 10-case outcome eval on a restored copy of production, with production models, judged only on what
happened (what reached the person, what was asked, what was done), never on wording or tool order.
Baseline: the system with the background agent still separate.

| Case | Separate background agent | One agent |
|---|---|---|
| A preference stated in chat holds in background work | 1 of 3 | 3 of 3 |
| A reassignment arriving by mail is taken | 0 of 3 | 3 of 3 |
| The new owner's agent sees the reassignment | 0 of 3 | 3 of 3 |
| A direction given in chat becomes owned, ongoing work | 0 of 3 | 4 of 4 |
| A morning check is listed where the person sees it | 0 of 3 | pass |
| Two mails on one matter produce one message | fail * | pass |
| A quiet day produces no message, question or push | 3 of 3 | pass |
| Mail needing a reply is prepared and nothing is sent | 3 of 3 | pass |
| Tool searches per turn | 6.8–17.6 | 1.5–4.0 |
| Repeated searches per run | 32–69 | 0–18 |

\* The separate agent "passed" this case only because its messages never reached the person at all.
Once they did, it sent two.

Every case that improved is a coherence case: something said or learned in one place had to shape
what happened in another. The cases that already passed (quiet days, not sending without approval)
stayed passing.

The agent's model spend on the ten cases rose from $0.71–$0.99 to $1.72 per run. That is work the split
system never did: background turns now carry the person's context, and work handed to a colleague
wakes the colleague's agent, which is why the reassignment cases pass.

### Less system

| | Before | After |
|---|---|---|
| Planner loops | 2 | 1 |
| Agents with their own context | 3 kinds | 1 per person |
| Hub tools / loop built-ins / tools listed per turn | 272 / 22 / 22 | 125 / 10 / 20 |
| Repeat guards | 7 | 0 |
| Application code removed | | about 48,000 lines (40,000 net) |

## Pitfalls we hit building it

None of these follows from having one agent. They are mistakes we made carrying it out, each fixed
within about a week, and they are the ones other teams are most likely to repeat.

- **Do not strip schemas from tool-search results to save tokens.** We assumed found tools would join
  the visible tool list; when the list was full they did not, so the agent found tools it could not
  call and searched for the same tool up to 124 times in one turn. Return the full schema with every
  hit.
- **Do not let a retry ask for the whole output budget.** After a cut-off reply, one retry reasoned
  through 131,072 tokens without writing. Grow the budget step by step. (The earlier retry, which turned
  reasoning off, was worse: twice it claimed a record was saved when it was not.)
- **Do not store a person's background agent as an ordinary task.** Marking the task done ended the
  person's background help for days.
- **Do not let the agent's own writes wake it.** One chat edit started four background runs; one call
  started seven. Wake on what changed outside the agent.

## What we think this generalises to

- **Split by who the work is for, not by what kind of work it is.** One agent per person, with that
  person's context and permissions. Specialisation by task (a research agent, a mail agent, a
  follow-up agent) creates agents that share a person but not a context.
- **Context is the coordination mechanism.** Agents that cannot see each other's state coordinate
  through guards, queues and review passes. One context makes most of that machinery unnecessary.
- **Background is a trigger, not an agent.** What differs between chat and background is what starts
  the turn and whether someone is waiting. Neither needs a different agent.
- **Guards are a smell.** A repeat guard, a dedupe rule or a review pass bolted onto runs is evidence
  that some agent is deciding without the context it needs. Remove the split rather than add the guard.
- **Measure by outcomes on real state.** The improvements above were invisible to tests of individual
  components; they show only when the whole agent runs on a copy of production and what reached the
  person is judged.

## How we measured

- **Background calls and spend:** read-only aggregates from the system's model-call ledger, split by
  whether a turn was started by a person or by an event. The "before" week is the last full week
  before the specialised pipelines were deleted.
- **Outcome eval:** ten cases on restored copies of production, with the production models and the real
  scheduler. Baseline and the first two steps ran three times each; later steps once each, against the
  stored result of the step before, rerunning any case that fell.
- **Models:** DeepSeek V4.1 Flash through OpenRouter, in chat and background alike.
- **Price of a call:** cheaper hosting for unattended calls started a week before the consolidation.
  It is why the per-call price is similar on both sides, and why the saving above is counted in runs.

## Related work

**For and against one agent**

- Yan (Cognition), "Don't Build Multi-Agents", 2025-06-12. https://cognition.com/blog/dont-build-multi-agents.
  "Share context" and "actions carry implicit decisions". Our four approvals for one email are what it
  predicts. We agree, and extend it from sub-agents to background agents.
- Sarkis (Anthropic), "Building agents: When to fold subagents into your main agent loop", 2026-10-22.
  https://claude.com/blog/building-agents-when-to-fold-subagents-into-your-main-agent-loop. One loop
  with tools found as needed; keep subagents only where context size, parallel work or conflicting
  instructions require them; build an end-to-end eval first and fold one piece at a time. We followed
  the same route and found no part of this system that needed to stay separate.
- Schluntz and Zhang (Anthropic), "Building effective agents", 2024-12-19.
  https://www.anthropic.com/engineering/building-effective-agents. Workflows suit well-defined tasks,
  agents suit open-ended ones, start simple. The pipelines we deleted were workflows built for work
  that turned out not to be well-defined.
- Hadfield et al. (Anthropic), "How we built our multi-agent research system", 2025-06-13.
  https://www.anthropic.com/engineering/multi-agent-research-system. Multi-agent research wins on
  broad, parallel questions at about 15 times the tokens of chat, and fits poorly where agents must
  share context. Work done for one person is that poor fit.
- Cemri et al., "Why Do Multi-Agent LLM Systems Fail?", 2025. https://arxiv.org/abs/2503.13657.
  Fourteen failure modes from over 1,600 traces. Our failures before the change are its inter-agent
  misalignment group: agents ignoring each other's state and repeating work.
- Tran and Kiela, "Single-Agent LLMs Outperform Multi-Agent Systems on Multi-Hop Reasoning Under Equal
  Thinking Token Budgets", 2026. https://arxiv.org/abs/2604.02460. Many reported multi-agent gains come
  from extra compute that was not counted.
- Kim et al., "Towards a Science of Scaling Agent Systems", 2025. https://arxiv.org/abs/2512.08296.
  Multi-agent overhead hurts tool-heavy, sequential tasks most, which is what operational work is.
- Gao et al., "Single-agent or Multi-agent Systems? Why Not Both?", 2025. https://arxiv.org/abs/2505.18286.
  The advantage of multi-agent systems shrinks as models improve.

**Context**

- Hong, Troynikov, Huber (Chroma), "Context Rot", 2025-07-14. https://www.trychroma.com/research/context-rot.
  Performance falls as input grows. This is the price of one context: our prompts average 64,000–81,000
  tokens, and replies that are all reasoning rise from 0.3% of calls under 50,000 tokens to 6.7% above
  150,000. We cap conversation history and keep older turns searchable instead of splitting the agent.
- Rajasekaran et al. (Anthropic), "Effective context engineering for AI agents", 2025-09-29.
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents. Context as a finite
  resource; compaction for long conversations, clean sub-agent windows for parallel research.

**Background agents**

- Chase (LangChain), "Introducing ambient agents", 2025-01-14.
  https://www.langchain.com/blog/introducing-ambient-agents. Agents driven by events, reaching people by
  notifying, asking or asking for review. We arrived at the same three, with one difference: the
  event-started agent is the chat agent itself.
- Garimella (Actively), "Human-agent collaboration for long-running agents", 2025-10-31.
  https://www.actively.ai/blog/human-agent-collaboration. The opposite design: a long-running background
  agent per account with short-lived chat agents reading its memory. Our intermediate design was close
  to this, and it is where the fragmentation above came from.
