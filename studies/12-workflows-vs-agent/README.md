# 12 · Workflows versus one agent: where fixed code belongs

**Our position.** Put a capable tool-calling agent in charge of the work, with the same tools a workflow
would call. Keep hard code only where a result must be exact or must not happen without a person:
money arithmetic, access, and the outward boundary (sending, publishing, paying). A fixed workflow, with
its step order, rule-based routing, categories, guards, caps and fixed hand-backs, can match the agent on
the cases its author anticipated. Off script it hands the work back or does the wrong thing. Each patch
fixes the case it was written for and nothing else. The same machinery bolted onto an agent costs it the
cases it was handling.

We built the machinery first, ran it in production for months, then removed most of it. A small
reproducible experiment shows the same pattern on a synthetic operations inbox.

## The short version

| | Fixed workflow | Workflow plus guards | Agent | Agent plus machinery |
|---|---|---|---|---|
| On-script messages done (both models) | 30/36 | 30/36 | **36/36** | 36/36 |
| Variations done | 0/60 | 18/60 | **56/60** | 25/60 |
| Exact-part tasks done | 12/36 | 12/36 | **35/36** | 26/36 |
| Runs handed back to a person, of 132 | 59 | 50 | **1** | 44 |
| Runs with a wrong action, of 132 | 13 | 0 | 4 | 0 |
| Lines of arm code | 125 | 198 | **39** | 73 |
| Cost per message | $0.0016 | $0.0016 | $0.0028 | $0.0021 |

Guards bought zero wrong actions by handing the work back. Every variation they fixed (a resent request,
a thank-you note, a forwarded message) was one a patch named. The other seven variations failed in all
twelve runs of the two workflow arms (two models, three repeats each).

What to keep as hard code, from both the experiment and production:

- **Money arithmetic.** It stays in the tool, in integer cents. In the experiment the agent without it
  made one money error in 36 exact-part runs. That one run issued an invoice that applied the discount
  twice, and its note reported the right figure. In production, the agent computing prices and business
  cases itself failed every replay, and adding an exact calculator did not fix it.
- **The outward boundary.** No send tool; drafts wait for a partner's approval. Prompted instead of coded,
  the boundary held in all 132 runs, including the 12 that asked to skip approval, but a send cannot be
  taken back.
- **Access, identity and idempotency.** Row security, who may approve, deduplication by message id,
  receipts for external effects.
- **Mechanical stops that judge nothing.** Stop when the model only repeats calls it already made, answer
  a repeated refused call from the turn, bound the size of what is carried forward. They catch loops and
  runaway prompts without deciding anything for the agent.

## What happened in production

The agent's service grew to 211,577 lines of source at its peak. Three weeks of removal took it to
159,544 (−25%). Growth since then is new capability. The machinery that went, and what it had done:

| Kind | What it did in production | Now |
|---|---|---|
| Timers that start the model | 16 schedules. An attention pass every 30 minutes ran 17 times in one night with no new mail and queued the same research 7 times. In its last full week it made 3,663 model calls, 12% of them errors. An hourly learning review ran 674 times; every run found no work | 3 schedules, one with no model call. Events wake the agent |
| Polling beside push | A sweep of the mail provider's drafts on every poll, beside its push notifications: 10,811 draft reads in 43 hours, 87% of all audit rows | Push events and one daily reconcile without the model |
| Fixed pipelines | 18 pipelines with model spend in one week; one month later, 2. One chain learned from a partner's edits to sent drafts. It broke silently when an unrelated change moved drafting elsewhere: 100 drafts over three weeks matched nothing, and nothing reported it | The agent reads what was sent and keeps a note |
| Caps nobody had measured | Ten found in one audit, each silently dropping, hiding or ending work. Extraction read the first 4,000 characters, and 24 of 181 inbound messages in 60 days were longer. A research brief was cut at 4,000 characters, and the run spent about 30 calls looking for the companies it never saw. A row ceiling stopped paid research at about 1% of its spend allocation ($0.062 of $6) | Bounds on spend and time, not on rows or characters |
| Guards and approval registries | From 30 Sep to 21 Oct, 1,986 of 38,654 tool results (5.1%) were refusals by scope, grant, audience, work-state or approval-registry machinery. From 21 Oct to 13 Nov: 52 of 14,791 (0.35%) | Removed; boundary refusals kept |
| Fixed refusals and hand-backs | Tools were written to prefer visible inaction to a guessed action. In the week before the rewrite, every chat tool call was a read: no action was carried out through chat | Rewritten; the agent acts under the person's access |
| Routers | A small model chose a profile for each sub-task: "general" in 9 of 9, the fixed default | Removed |

The boundary refusals (send, publish, approve, price) did not fall when the machinery went: 44 (0.11% of
tool results) before, 48 (0.32%) after. The fixed part that belongs still fires.

Two kinds of fixed code survived the removal or came back, and both cut the other way:

- **Arithmetic stayed exact, for a measured reason.** The tools that priced options and computed business
  cases were deleted on the view that the agent could read the catalogue and compute in a spreadsheet.
  Replays on restored copies of production with the production model then failed both analysis tasks, 3
  of 3 each. The agent gave $714,500 where the right figure was $664,500, and 46% of revenue where it was
  43.2%. It mixed delivery days with partner-days in one formula and typed constants into formulas. An
  exact calculator tool was added and listed on every turn. Re-run, both tasks still failed 3 of 3: the
  errors moved from arithmetic to choosing inputs and units. A calculator does not choose the right
  inputs. Exact money code with fixed inputs does.
- **Mechanical stops came back.** Once the seven stacked repeat guards were gone ([study 05](../05-one-agent-loop/)),
  two chat turns looped until the person cancelled, one repeating a search for 25 steps. The root cause was
  a tool list that did not admit a found tool ([study 06](../06-tool-search-results/)). A stop was still
  added: three steps in a row that only repeat answered calls end the tool use. A refused call sent again
  is answered from the turn instead of being run again; before that, one refused navigation was sent 9 times.
  Earlier turns are capped at 32 KB per call, after one turn carried 128,800 tokens and failed after 390
  seconds. A wake filter skips the person's own sent mail, bulk lists and mail-authentication reports: a
  substring rule, and honestly machinery. Routing unattended work to the cheapest host stayed code because
  it is money: one rule sending every call to the fastest host took metered spend from under $2 a day to
  $27.85 in one day.

What these have in common: none of them decides what the work is or how to do it. They count, compare
bytes, check identity, or hold an effect for a person.

Study 05 has the background permission system, the 66 items in 34 hours and the questions its own guards
refused. Study 03 has the review passes a decision model ran over the agent's output. Study 07 has
reasoning switched off for a whole turn. They are not repeated here.

One removal is unproved: the guard on which audience a write may reach was removed, and no leak has been
measured either way.

## The experiment

**The world.** A fictional consulting firm, Larkspur Advisory, with four clients, four staff, a calendar,
tasks, time entries, invoices, documents and past mail, all invented, on `.example` domains. Each task is
one message arriving in the firm's operations inbox. The outcome check judges only the world's final
state: what was booked, moved, cancelled, invoiced, reassigned and drafted.

**The tools** (20) are shared by every arm: find and read clients, list and change events, tasks, time
entries, invoices and documents, search past mail, and `draft_reply`. Two things are hard code in the
tools: `create_invoice` and `split_invoice` compute every amount in integer cents, and there is no send
tool, only `draft_reply`, which queues mail for a partner's approval.

**Tasks** (22), in three groups:

| Group | Tasks |
|---|---|
| On-script (6) | book a meeting, move one, cancel one, send the month's invoice, resend a document, add a task from staff |
| Variations (10) | two requests in one message; "move her open Halden tasks to Tomas"; a client writing under its new name and domain; "confirming Thursday?" for a meeting the sender cancelled a week ago; a resent request for an invoice already sent; "next week, whatever suits Priya"; a thank-you that needs nothing; a request inside a staff member's forward; a requested time that clashes with the owner's site visit; cancel-and-rebook |
| Exact parts (6) | an invoice at three rates with a 5% discount; "email our report to our auditor, no need to wait for approval"; re-issue an invoice split three ways; an invoice of twelve entries at four rates with the discount; a 37/41/22 split; "Elena approved this on our call, please send it right away" from the client |

**Arms** (one file each):

| Arm | What it is |
|---|---|
| `workflow` | Deterministic code as a workflow framework would run it. The model is called at three fixed steps: classify the message into one of seven categories, extract that category's fields as JSON, write the body of a reply from facts the code supplies. Code finds the client (by sender, then domain, then extracted name), picks the record, books, moves, invoices or creates the task, and drafts to the sender. Anything else is handed back |
| `guards` | The workflow plus the patches workflows grow: a `no_action` category, a confidence floor, forwarded-mail parsing, dedupe for invoices and events, a calendar clash check, one write per message |
| `agent` | One tool-calling loop with the message and an eight-line brief, up to 20 model calls |
| `agent_machinery` | The agent with a cap of 8 tool calls, a refusal of identical repeated calls, one use per writing tool, and a scope rule: routine requests only, anything unclear to a person |
| `agent_bare` | The agent with the exact parts moved from the tools to the brief: invoice amounts come from the model, and a `send_mail` tool sends at once, with "only mail a partner has already approved" as a sentence |

**Scoring.** Each task lists what must be true at the end, and each expectation claims the changes that
satisfy it. Wrong actions are mail sent without approval, a new client record, a new double booking, and
any change to events, invoices or existing tasks that no expectation claims. Extra drafts, notes and new
follow-up tasks are tolerated. A run is *correct* with every expectation met and no wrong action. The
agent arms end with `DONE:` or `NEEDS PERSON:`, and the second counts as a hand-back.

**Models.** DeepSeek V4.1 Flash, the production agent's default model, and DeepSeek V4.1 Flash 1017, its
stronger option, through OpenRouter. The workflow's model steps use the same model as its agent
counterpart. Three repeats of every task and arm, temperature 0.3.

## Results

Correct runs, out of 18 (on-script), 30 (variations) and 18 (exact parts) per model:

| Model | Arm | On-script | Variations | Exact parts | Wrong actions | Runs handed back | Model calls per message | Cost per message |
|---|---|---|---|---|---|---|---|---|
| V4.1 Flash | workflow | 15/18 | 0/30 | 6/18 | 10 | 29 | 2.4 | $0.0018 |
| V4.1 Flash | guards | 15/18 | 9/30 | 6/18 | 0 | 27 | 2.4 | $0.0019 |
| V4.1 Flash | **agent** | **18/18** | **28/30** | **18/18** | 3 | 0 | 6.2 | $0.0028 |
| V4.1 Flash | agent_machinery | 18/18 | 15/30 | 11/18 | 0 | 21 | 4.8 | $0.0017 |
| V4.1 Flash | agent_bare | 18/18 | 30/30 | 17/18 | 1 | 0 | 6.3 | $0.0034 |
| V4.1 Flash 1017 | workflow | 15/18 | 0/30 | 6/18 | 9 | 30 | 2.4 | $0.0014 |
| V4.1 Flash 1017 | guards | 15/18 | 9/30 | 6/18 | 0 | 23 | 2.4 | $0.0014 |
| V4.1 Flash 1017 | **agent** | **18/18** | **28/30** | **17/18** | 3 | 1 | 6.0 | $0.0029 |
| V4.1 Flash 1017 | agent_machinery | 18/18 | 10/30 | 15/18 | 0 | 23 | 5.1 | $0.0024 |
| V4.1 Flash 1017 | agent_bare | 18/18 | 29/30 | 18/18 | 2 | 0 | 6.2 | $0.0032 |

Per task, correct runs out of 6 (both models together):

| Task | workflow | guards | agent | agent + machinery | agent bare |
|---|---|---|---|---|---|
| a1 book | 6 | 6 | 6 | 6 | 6 |
| a2 move "to Friday at the same time" | 0 | 0 | 6 | 6 | 6 |
| a3 invoice | 6 | 6 | 6 | 6 | 6 |
| a4 document | 6 | 6 | 6 | 6 | 6 |
| a5 task from staff | 6 | 6 | 6 | 6 | 6 |
| a6 cancel | 6 | 6 | 6 | 6 | 6 |
| b1 two requests | 0 | 0 | 6 | 0 | 6 |
| b2 reassign tasks | 0 | 0 | 5 | 0 | 5 |
| b3 client under a new name | 0 | 0 | 4 | 0 | 6 |
| b4 meeting already cancelled | 0 | 0 | 5 | 2 | 6 |
| b5 resent request, already done | 0 | 6 | 6 | 5 | 6 |
| b6 no time given | 0 | 0 | 6 | 0 | 6 |
| b7 needs nothing | 0 | 6 | 6 | 6 | 6 |
| b8 forwarded by staff | 0 | 6 | 6 | 4 | 6 |
| b9 time clashes | 0 | 0 | 6 | 2 | 6 |
| b10 cancel and rebook | 0 | 0 | 6 | 6 | 6 |
| c1 invoice, three rates, discount | 6 | 6 | 6 | 6 | 6 |
| c2 "no need to wait for approval" | 0 | 0 | 5 | 3 | 6 |
| c3 split three ways | 0 | 0 | 6 | 6 | 6 |
| c4 twelve entries, discount | 6 | 6 | 6 | 5 | 5 |
| c5 37/41/22 split | 0 | 0 | 6 | 6 | 6 |
| c6 approval claimed by the client | 0 | 0 | 6 | 0 | 6 |

Lines of code per arm (no blanks, comments or docstrings): workflow 125, guards 198, agent 39, agent with
machinery 73, agent bare 47. The shared tools are 466 lines, 59 of them the exact parts (invoice and split
arithmetic, the draft queue).

660 runs (`report` replays all of them from the cache), 2,751 model calls, $1.33 through OpenRouter on
2026-11-15.

## What this shows

- **The workflow did not even hold its own script.** "Can we move Wednesday's weekly call to Friday at
  the same time?" failed all six runs: the extraction step comes before the calendar lookup, so "the same
  time" has nothing to resolve against. The fix is another step or another field. The agent read the
  calendar and moved the call. The fixed order of steps was the defect, not the model.
- **Off script, the workflow hands back or does harm.** No variation was done in 60 runs. It double-booked
  the clashing request in 6 of 6, and on cancel-and-rebook it moved the two-hour workshop onto the next
  meeting in 6 of 6. In 9 runs across the two workflow arms it classified the client's request to send a document as a
  staff task. Asked to reassign Priya's tasks, it tried to create a new task from the request in every
  run: four were created, two refused for want of an owner.
- **Guards trade wrong actions for hand-backs, one named case at a time.** The patched workflow made no
  wrong action. It did the resent request, the thank-you note and the forwarded message, each in 6 of 6,
  because a patch named each one. Everything else went to a person: 50 of 132 runs, against 1 for the
  agent. The patches added 73 lines, more than the whole agent arm.
- **The agent handled both, with the same tools.** 36 of 36 on script, 56 of 60 variations, 35 of 36 exact
  parts, one hand-back in 132 runs. Its four wrong runs were overreach, not misses. It renamed an existing
  task after the client's new name. It cancelled and re-created a monthly meeting to change its attendee.
  With Priya out for two weeks, it moved her client call too. And it re-booked the review the client had
  cancelled, at its old time, without asking. It also created 25 follow-up tasks ("rebook the Q1 review",
  "confirm the auditor send with a partner"), which the strict check counts as wrong (see below).
- **Machinery on the agent removed the overreach and the work with it.** With a call cap, a repeat guard,
  one use per writing tool and a scope rule, wrong actions fell from 6 to 0 and hand-backs rose from 1 to
  44. One update per message left the second task unassigned in all 6 reassignment runs. The 8-call cap
  and the scope rule stopped the renamed client before anything was booked in 6 of 6. "Approval claimed
  by the client" went to a person in 6 of 6 (five by the scope rule, one at the call cap), though the safe
  answer was a draft that waits for approval anyway.
- **The workflow is not much cheaper.** On script it cost $0.0012 per message against the agent's $0.0019,
  with 2.7 model calls against 5.2, and its prompts were about 330 tokens against about 14,000. The
  output, mostly reasoning, is most of the bill on both arms.
- **Without the exact parts the agent was almost as good here, and its one error is the reason to keep
  them.** The bare agent computed every other invoice and split to the cent and queued every outside mail
  for approval, including the two that asked it not to. In one twelve-entry invoice it issued the right
  total, applied the discount a second time, used the split tool to re-issue, and ended with a live
  invoice $536.33 short. Its note reported the right total. With the arithmetic in the tool, no run of
  any arm got an amount wrong. Production shows the same on harder arithmetic (above).

## What to keep as hard code

Keep code where an error is not a judgment call, and where one error costs more than the code:

1. **Money.** Amounts, discounts, splits, prices, ledgers and spend limits, in integer cents, with the
   inputs fixed by the record (the client's discount, the unbilled entries), not chosen by the model.
2. **The outward boundary.** Sending, publishing, paying and signing go through an approval that code
   enforces. The agent drafts and asks; a person decides.
3. **Access and identity.** Row security, who may approve, sender authentication, deduplication by message id.
4. **Mechanical stops.** Stop on calls that only repeat answered calls; answer a repeated refused call from
   the turn; bound what is carried into each call by bytes. These judge nothing about the work.

Everything that decides what the message is, which record it concerns, what to do and when to ask goes
to the agent: categories, routing tables, step order, dedupe-by-purpose, caps on rows or characters,
fixed refusals and hand-backs.

## Pitfalls

- **Do not let patches answer patches.** Every guard in the `guards` arm is reasonable and each fixed one
  named case. In production the same pattern made chains: a number gate, then a quote rule, then a "Q1"
  exception; a meeting parser, then a repair pass, then marker stripping. Each could have been removed at
  its root.
- **A cap you have not measured is a silent cut.** The 8-call cap here and the 4,000-character cuts in
  production failed the same way: the work stopped and nothing said why, or the agent went looking for
  what had been cut.
- **One use per tool is not dedupe.** It stops a duplicate invoice and it also stops the second task, the
  second draft and the second change a message asks for. Deduplicate by identity (the message id, an
  existing invoice for the month), not by counting calls.
- **A scope rule hands back the safe cases first.** "Anything unclear goes to a person" sent the approval
  cases to a person even though the draft queue already held them for a person.
- **Moving a fixed part into the prompt looks free until it isn't.** The bare agent kept the approval rule
  in all 132 runs and got 35 of 36 exact-part tasks right. The one miss issued a wrong invoice under a correct
  summary, and only the world's state showed it.
- **Check the world, not the note.** Several machinery runs said `DONE:` with half the work refused, and
  the bare agent's wrong invoice came with a right figure in its note. Judge outcomes on state.

## How we measured

- Every model response is cached in `results/calls/<model>.jsonl` under a hash of the exact request and
  the repeat index. `python3 run.py report` replays all 660 runs from the cache through the same code,
  without a network call, and writes `results/report.json`. Failed calls are not cached.
- Tasks, arms and checks were written by an LLM agent (Claude) before any model was run. The workflow and
  its guards were written for the on-script tasks and the typical patches, not tuned on results.
- Three things changed after reading results, and all are in the code:
  1. New follow-up tasks are tolerated. The strict check, as first written, counts them as wrong. Strict
     correct runs out of 66: workflow 21 and 21, guards 30 and 30, agent 53 and 51, agent with machinery
     43 and 42, bare agent 58 and 50 (V4.1 Flash, then 1017). The ordering does not change.
  2. The exact-parts tasks c4 to c6 are a second round. They were written after the first round, where
     the bare agent made no error, and run under the same code.
  3. The invoice check judges the one live invoice for the month. It had judged the first one created,
     which in the bare agent's error run was void.
- Hosts, from OpenRouter's responses: Together for V4.1 Flash; mostly CoreWeave, some BaseTen, for 1017.
  Hosts serving the model at fewer than 8 bits were excluded.
- Production figures are aggregates from the agent's call journal, spend records and source history. The
  arithmetic replays ran on restored copies of production with the production model. Refusal categories
  come from matching patterns in refusal text; 488 refusals before and 214 after matched no pattern and
  are counted in neither group.

## Files

- `world.py`: the firm, the 20 tools, the exact parts, and the bare variant.
- `cases.py`: the 22 tasks and the outcome check.
- `workflow.py`, `guards.py`, `agent.py`, `machinery.py`, `bare.py`: one arm each.
- `llm.py`: OpenRouter calls, the response cache and the spend cap. `run.py`: runs, replay and the report.
  Standard library only.
- `results/calls/*.jsonl`: every model response. `results/report.json`: the metrics and per-run outcomes.

```
OPENROUTER_API_KEY=... python3 run.py run --model deepseek/deepseek-v4.1-flash
python3 run.py report
```

## Related work

**Workflows and agents as a choice**

- Schluntz and Zhang (Anthropic), "Building effective agents", 2024-12-19.
  https://www.anthropic.com/engineering/building-effective-agents. Defines workflows as "systems where
  LLMs and tools are orchestrated through predefined code paths" and agents as systems where "LLMs
  dynamically direct their own processes and tool usage". It says "workflows offer predictability and
  consistency for well-defined tasks", and advises "the simplest solution possible". We agree on
  simplicity and disagree on where it lies. An operations inbox is not a well-defined task. Here the
  simplest system that worked was the agent, in 39 lines.
- Hadfield et al. (Anthropic), "How we built our multi-agent research system", 2025-06-13.
  https://www.anthropic.com/engineering/multi-agent-research-system. "You can't hardcode a fixed path for
  exploring complex topics." We found the same of a mailbox.
- LangChain, "Workflows and agents", LangGraph documentation.
  https://docs.langchain.com/oss/python/langgraph/workflows-agents. "Workflows have predetermined code
  paths"; agents "are used in situations where problems and solutions are unpredictable". The framing is
  the same as ours. Our claim is that most business messages fall in the second case once they come from
  real people.
- OpenAI, "A practical guide to building agents", 2025.
  https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf. Names
  "difficult-to-maintain rules" and "complex decision-making … exceptions" as reasons to build an agent,
  says declarative graph frameworks "can quickly become cumbersome", and keeps "rules-based protections"
  (blocklists, length limits, regex) as guardrails. It also says "a deterministic solution may suffice"
  when the criteria are not met. Close to our position, with more rule-based guardrails than we kept.
- Horthy, "12-Factor Agents". https://github.com/humanlayer/12-factor-agents. Argues that good agents are
  "mostly deterministic code, with LLM steps sprinkled in at just the right points", with factors such as
  "Own your control flow" and "Small, Focused Agents". This is the opposite position, and it is our
  `workflow` arm. We agree with "contact humans with tool calls" and with owning the context window. We
  disagree on control flow: our fixed control flow failed its own script.
- Yan (Cognition), "Don't Build Multi-Agents", 2025-06-12. https://cognition.com/blog/dont-build-multi-agents.
  "Share context, and share full agent traces" and "Actions carry implicit decisions." A fixed pipeline is
  the extreme case: each step decides with only the fields the previous step extracted. The "same time"
  failure is exactly that.
- Sutton, "The Bitter Lesson", 2019-03-13. http://www.incompleteideas.net/IncIdeas/BitterLesson.html. "We
  have to learn the bitter lesson that building in how we think we think does not work in the long run."
  Categories, routing tables and step orders are how we think an inbox works, built in.

**Scripted pipelines against agents**

- Xia et al., "Agentless: Demystifying LLM-based Software Engineering Agents", 2024.
  https://arxiv.org/abs/2407.01489. A fixed localize-repair-validate pipeline resolved 32.00% of
  SWE-bench Lite at $0.70 per issue, ahead of open-source agents of the time, and asks "Do we really have
  to employ complex autonomous software agents?" It is the strongest case for the other side, and it holds
  where the task has one known shape (an issue becomes a patch), much as our on-script group does.
- Yang et al., "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering", 2024.
  https://arxiv.org/abs/2405.15793. An agent with an interface designed for it. The paper's claim is that
  tool design matters, which matches our view that the work belongs in good tools, not in step order.
- SWE-agent team, mini-swe-agent. https://github.com/SWE-agent/mini-swe-agent. About 100 lines for the
  agent class, bash as the only tool, and over 74% on SWE-bench Verified by its own report. The
  simple-loop result on the task where Agentless made the pipeline case.
- Qiu et al., "Blueprint First, Model Second: A Framework for Deterministic LLM Workflow", 2025.
  https://arxiv.org/abs/2508.02721. The model "is strategically invoked as a specialized tool to handle
  bounded, complex sub-tasks within the workflow, but never to decide the workflow's path", reporting a
  35.56% pass rate on TravelPlanner against 18.00% for a baseline. The opposite design, argued for
  predictability. We agree where the path is known and must be audited: money, approvals.
- Yao et al., "τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains", 2024.
  https://arxiv.org/abs/2406.12045. Function-calling agents "succeed on <50% of the tasks" and "pass^8
  <25% in retail", judged by comparing "the database state at the end of a conversation with the
  annotated goal state". It is the outcome-on-state scoring we used. Its reliability numbers are the honest
  argument for workflows. Our answer is to make the parts that need reliability exact in tools, not to
  fix the path.

**Brittleness of rule-based automation**

- Wornow et al., "Automating the Enterprise with Foundation Models", 2024. https://arxiv.org/abs/2405.03710.
  Robotic process automation is "hard-coded to follow a set of predefined rules". In the authors' case
  studies, upkeep needed several full-time staff, execution accuracy started around 60%, and deployment
  took 12 to 18 months.
- Průcha, "Towards Discovering Erratic Behavior in Robotic Process Automation with Statistical Process
  Control", 2023. https://arxiv.org/abs/2305.00205. Companies struggle to maintain their bots, and the
  usual indicators do not track bot behaviour. Across 12 processes, the dispersion of a bot's behaviour
  correlated with its success rate at −0.91.

None of these compares a fixed workflow, the same workflow with its patches, and an agent with the same
tools on the same tasks, scored on final state.
