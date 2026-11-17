# 07 · Reasoning off for one decision, not for the turn

**My position.** Reasoning belongs to a single decision, not to a whole turn. When one decision
reasons through its whole output budget and answers nothing, ask that decision again with a bigger
budget and reasoning still on. Never turn reasoning off for the rest of the turn: every later decision
then pays for one decision's failure. Turning it off for just the retry is a weaker fix than a bigger
budget, because a reply written without reasoning can claim work that never happened, and in
production one did.

(Each model call has an output budget, its *room*: reasoning and answer share it. A decision "runs out
of room" when reasoning uses all of it.)

**The evidence.** I ran all three fixes in my production agent. Reasoning off for the rest of the turn
lasted three hours. Off for the one retry lasted two weeks. A bigger budget with reasoning on is what
runs now.

- **Off for the rest of the turn made the agent repeat itself in production.** DeepSeek V4.1 Flash sent
  a rejected document update 19 and 23 times; DeepSeek V4 Flash 0731 created the same file 29 times. In
  background runs where reasoning was off by mistake, 17.8% of steps repeated the previous call exactly,
  against 1.3% in chat, where it was on.
- **Off for the one retry claimed work that never happened.** Its last production failure answered, in
  text, that a meeting record was saved and two promises booked. Nothing was.
- **In a reproducible experiment, off for the turn got less done on the default model and did no
  better than reasoning on with any model.** V4.1 Flash finished 41 of 90 turns with it, against 58
  with a bigger budget and 59 with reasoning on throughout. On V4 Flash 0731 the fixes were within
  one turn of each other; on Qwen3.6 every fix trailed reasoning-on.
- **A bigger budget costs almost nothing:** one extra call per turn, about $0.00005 on V4.1 Flash.

**What the experiment does not show.** It did not reproduce the repeated calls, and false claims were
rare in every arm, slightly commoner with reasoning on. Its turns were about 9,000 tokens; the
production loops came from prompts of 64,000 to 81,000. Those two findings rest on production.

**Status.** Design position, with production data and a small reproducible experiment (synthetic data,
every response committed, $2.41 for all hosted runs).

## What happened in production

The agent is one tool-calling loop. Its models (DeepSeek V4.1 Flash by default, DeepSeek V4 Flash 0731
for fast turns) reason before each decision, and a decision whose reasoning uses up its output room
returns neither an answer nor a tool call.

| Date | Rule for a decision that ran out of room | What happened |
|---|---|---|
| until 10-06 | 2,400 tokens, then doubled, then once with reasoning off | 17 chat decisions in two weeks reasoned through 2,400 and 4,800 tokens. I raised the room to 16,384 |
| 10-07 | Ask that decision again with reasoning off, then on again | Fixed the single call. On a captured rewrite decision, reasoning on ran out 3 of 3 times on both models; off, 0 of 6 ran out and 6 of 6 called the tool. But the next decision often re-read the article and ran out again: 10 times in 3 test runs, about 25 of 57 minutes |
| 10-07 | Keep reasoning off for the rest of the turn | Each turn ran out once, but V4.1 Flash sent a refused document update 19 and 23 times, and V4 Flash 0731 created the same file 29 times. I reverted it three hours later |
| 10-07 to 10-21 | Off for that one decision only | Kept. A retry with no reasoning was the fast path out of a decision that did not converge |
| 10-21 | Removed | A decision that would write a meeting record reasoned through its whole 17,408 tokens. The retry, with no reasoning, answered in text: once that the record was saved and two promises booked (nothing was), once that the record was someone else's to write |
| 10-21 | The same decision again, reasoning on, with the route's whole room (131,072 tokens) | 16 of 20 retries answered in 1,800 to 17,000 tokens. 4 reasoned through all of it for nothing, at $0.16 and 3 to 5 minutes each |
| 10-22 to now | Reasoning on, twice the room it was cut at; the last try gets the whole room | Runs now |

Two more production numbers back the position:

- **Reasoning off by accident in background work.** A per-task model setting pinned reasoning off and
  replaced the loop's request for it. Over 14 days 697 of 3,917 background steps (17.8%) repeated the
  previous call exactly, against 1.3% in chat on the same model with reasoning on. Most of the
  repeats sat in seven runs, each sending one call 13 to 79 times.
- **The same decisions, replayed.** I asked the model again at those runs' real decisions, with
  their real history. Where a run first repeated, reasoning off repeated 1 of 18 times and on 0 of 17.
  Where it had already repeated three times, off repeated 4 of 21 times and on 0 of 20. Without
  reasoning a model already in a loop stays in it.

The cost of reasoning on was small and known: in chat, 37 of 649 reasoning calls (5.7%) used their
whole output on reasoning, and those go to the retry.

## The experiment

A minimal tool-calling loop (`turn.py`) on 15 synthetic tasks (`cases.py`). Each task is a request to
an operations assistant at an invented firm, after three earlier turns that bring the prompt to about
9,000 tokens (median 8,637). Seventeen tools stand over a small world of records. In every task the
tools refuse one call the request leads to, the same way every time the model sends it unchanged:

- **10 tasks with a readable refusal**, half naming what to do instead ("locked for direct edits;
  suggest_edit adds a tracked suggestion"), half only naming what is wrong ("refused: owner_only",
  "refused: name_taken (f_212)", an empty search).
- **5 tasks with an opaque, permanent failure** ("Request contains an invalid argument.", "503 backend
  unavailable", "internal"). One copies the production case: shorten a newsletter intro, then the
  tools reject both the document update and the suggestion with the same opaque error.

Arms. The squeeze sends the turn's second decision with 8 tokens of room, so the model reasons through
all of it and answers nothing, the production failure made on purpose:

| Arm | Squeezed decision asked again with | Later decisions |
|---|---|---|
| `on` | not squeezed | reasoning on |
| `off` | not squeezed | reasoning off throughout |
| `decision_off` | reasoning off, normal room (8,192) | reasoning on |
| `turn_off` | reasoning off, normal room | reasoning off |
| `decision_bigger` | reasoning on, normal room | reasoning on |

Every turn has at most 14 model calls. The loop does not pass reasoning back between decisions, as
in production now. Models: DeepSeek V4.1 Flash and DeepSeek V4 Flash 0731, the production chat models,
and Qwen3.6 35B-A3B, an open model with a thinking switch. All through OpenRouter with
`reasoning: {enabled: true|false}`. Six repetitions per task and arm, 450 turns per model.

**Outcomes**, judged on the world's state, not on wording:

- *done*: what the person needed happened (the suggestion added, the draft saved, the slot booked).
- *handed back*: the turn ended with a reply, without doing it, and without claiming it.
- *false claim*: a reply saying the refused action itself was done. I ask a judge model (V4.1
  Flash) one yes-no question, only of turns where that action never went through.
- *unfinished*: the turn hit 14 model calls.
- *repeated failed calls*: calls identical, name and arguments, to an earlier call in the turn that
  the tools refused or that came back empty.

### Results

90 turns per cell.

| Model | Arm | Done | Handed back | False claims | Unfinished | Repeated failed calls | Output tokens / turn | Cost / turn |
|---|---|---|---|---|---|---|---|---|
| V4.1 Flash | on | 59 | 23 | 3 of 57 | 5 | 11 | 1,207 | $0.00204 |
| V4.1 Flash | off | 35 | 55 | 0 of 59 | 0 | 2 | 338 | $0.00073 |
| V4.1 Flash | decision_off | 54 | 28 | 3 of 55 | 5 | 13 | 1,055 | $0.00190 |
| V4.1 Flash | turn_off | 41 | 49 | 0 of 64 | 0 | 3 | 369 | $0.00084 |
| V4.1 Flash | decision_bigger | 58 | 23 | 3 of 56 | 6 | 11 | 1,191 | $0.00209 |
| V4 Flash 0731 | on | 55 | 23 | 5 of 56 | 7 | 17 | 1,104 | $0.00291 |
| V4 Flash 0731 | off | 49 | 40 | 1 of 64 | 0 | 9 | 544 | $0.00225 |
| V4 Flash 0731 | decision_off | 54 | 29 | 2 of 60 | 5 | 12 | 976 | $0.00311 |
| V4 Flash 0731 | turn_off | 55 | 34 | 1 of 66 | 0 | 7 | 728 | $0.00277 |
| V4 Flash 0731 | decision_bigger | 54 | 23 | 5 of 55 | 8 | 17 | 1,083 | $0.00330 |
| Qwen3.6 35B-A3B | on | 50 | 35 | 3 of 63 | 3 | 24 | 994 | $0.00536 |
| Qwen3.6 35B-A3B | off | 41 | 47 | 1 of 64 | 1 | 19 | 271 | $0.00390 |
| Qwen3.6 35B-A3B | decision_off | 33 | 51 | 0 of 55 | 6 | 21 | 697 | $0.00542 |
| Qwen3.6 35B-A3B | turn_off | 34 | 54 | 1 of 59 | 1 | 17 | 457 | $0.00475 |
| Qwen3.6 35B-A3B | decision_bigger | 38 | 48 | 1 of 53 | 3 | 21 | 952 | $0.00586 |

"Done" can be at most 60: four of the opaque tasks cannot be done, only handed back. The squeeze ran
the DeepSeek decisions out of room every time (270 of 270 each). Qwen answered inside 8 tokens 93
times of 270, so a third of its squeezed turns never took the retry path.

### What the numbers say

- **Reasoning off makes the agent hand work back, not loop.** V4.1 Flash with reasoning off ended 55
  of 90 turns handing back to the person, against 23 with it on. Asked to book a call at a busy time,
  to find an invoice under a slightly wrong name, or to send a file too big to attach, it more often
  reported the refusal and asked. With reasoning on it read the refusal and took the other way.
- **Off for the turn is where that loss comes from.** V4.1 Flash: 41 done for the rest of the turn
  off, 54 for one decision off, 58 for a bigger room. On V4 Flash 0731 the arms barely differ (54 or
  55, and 49 off throughout). Qwen does worse than reasoning-on in every squeezed arm, 33 to 38 against
  50; for that model a squeezed decision costs work whichever retry follows.
- **Off for one decision fails where that decision needed thought.** On V4.1 Flash, in the task
  where the squeezed decision came right after an empty search, the off retry told the person the
  client was not on file and stopped; it found the invoice 2 of 6 times. With the bigger room it found
  it 6 of 6 times.
- **The bigger room is reasoning-on plus one wasted call.** Once the room suffices, the retried decision
  is the same request reasoning-on sends, so it continues the same way. The difference is the squeezed
  attempt: one extra call, $0.00005 a turn on V4.1 Flash and under $0.0005 on the others, and one
  fewer step under the cap.
- **No arm repeated refused calls more with reasoning off.** Repeats were a property of the task and
  the model. On the DeepSeek models most were retries of a "503 backend unavailable", which the models
  made more often with reasoning on and which ended in a saved draft: a fair retry, not a loop. The
  one real loop is the opaque newsletter task: on every Qwen arm (11 to 17 repeats, up to 6 turns at
  the cap), and on V4 Flash 0731 only in the arms that reason after the refusal (3 or 4 turns at the
  cap; none with reasoning off).
- **False claims are rare and slightly commoner with reasoning on** (V4 Flash 0731: 5 of 56 with it
  on, 1 of 66 for the rest of the turn off). The production incident behind removing the off retry
  was a 17,000-token decision; nothing here reasons that long.

## Why the experiment and production disagree on repetition

The production repeats came from turns with prompts averaging 64,000 to 81,000 tokens, many steps, and a
model that had already repeated two or three times. The replay above shows the effect is mostly there:
at a first repeat, off and on barely differ (1 of 18, 0 of 17); three repeats in, off stays in the loop
(4 of 21, 0 of 20). My synthetic turns are short and rarely reach a second repeat on the DeepSeek
models. I did not build a longer run; this study does not reproduce the 19 and 23 repeats.

What it does reproduce is the other half of the production decision: without reasoning the agent
does less of what the person asked, and turning reasoning off for the rest of the turn makes every later
decision pay for one decision's failure.

## The simple alternative

**Retry the same request.** The squeezed decision would run out again; in production the same
captured rewrite decision ran out 3 of 3 times with reasoning on and the same room.

**Lower the effort for every decision.** In production, low effort still ran out 2 of 3 times on the
rewrite decision, and on another decision it turned a tool call into text. The provider did not honour
a reasoning `max_tokens` (11,103 reasoning tokens under a 4,000 cap).

**Turn reasoning off everywhere.** Cheapest by far: $0.00073 per turn on V4.1 Flash against
$0.00204. It did 35 of 90 turns against 59.

## Pitfalls

- **Do not give the retry the whole ceiling.** A decision that does not converge reasons through
  131,072 tokens as readily as through 16,384. Double the room, and give the whole room only to the
  last try.
- **Do not let a reply without reasoning stand in for a write.** The off retry's worst failure was an
  answer saying a record was saved. If you keep an off retry, check that the reply's claims match the
  calls that ran.
- **Do not let a per-task setting override the loop's reasoning.** The 17.8% background repeats came
  from a model setting I chose on single-answer tests, which silently replaced the loop's request.
- **Count a retry of a transient failure separately from a loop.** Sending a call again after a 503 is
  a fair retry. Repeating a call refused for what it says is not.

## Files

- `cases.py`: the 15 tasks, the tools and their world, the earlier conversation, the outcome checks.
- `turn.py`: the agent loop, the five arms, the cache, the judge and the report. Standard library only.
- `results/calls/*.jsonl`: every model response, keyed by the request and repetition.
  `results/turns.jsonl`: every turn's trace and outcome. `results/report.json`: the table above.

```
OPENROUTER_API_KEY=... python3 turn.py run --model deepseek/deepseek-v4.1-flash --reps 6
python3 turn.py report --reps 6     # replays every turn from the cache, no calls
```

I wrote the tasks and checks before any model ran. After a first single run of the ten readable
tasks showed no repeats in any arm, I added the five opaque tasks and the earlier conversation, then
froze the set; the results above are the frozen set's only full run. At the same point I lowered the
squeeze from 32 tokens to 8, because at 32 a short tool call often fitted.

## Related work

**Reasoning per step**

- Yang et al., "Ares: Adaptive Reasoning Effort Selection for Efficient LLM Agents", arXiv
  2603.07915. https://arxiv.org/abs/2603.07915. A small router picks the reasoning effort for each
  agent step; one fixed low effort for every step loses accuracy, and per-step selection cuts reasoning
  tokens by up to 52.7%. The same unit as mine: the step, not the task.
- Anthropic, "Extended thinking". https://platform.claude.com/docs/en/build-with-claude/extended-thinking.
  Adaptive thinking lets the model decide "whether and how much to think on each request"; changing
  the thinking setting between requests invalidates the prompt cache, so a per-decision switch has a
  price on that API.
- OpenRouter, "Reasoning tokens". https://openrouter.ai/docs/guides/best-practices/reasoning-tokens.
  On chat completions a reply that reasons through its room returns `finish_reason: "length"` with
  empty content, billed; the advice is to raise the output limit or lower the reasoning. That is the
  case this study is about.
- DeepSeek, "Thinking mode". https://api-docs.deepseek.com/guides/thinking_mode. Thinking is a
  per-request switch, on by default; with tools, earlier reasoning must be passed back on DeepSeek's
  own API. OpenRouter's providers did not require it here or in production.
- Qwen, quickstart. https://qwen.readthedocs.io/en/stable/getting_started/quickstart.html. Hybrid
  models with a hard `enable_thinking` switch and per-turn soft switches.

**Too much reasoning, too little**

- Cuadron et al., "The Danger of Overthinking: Examining the Reasoning-Action Dilemma in Agentic
  Tasks", 2025. https://arxiv.org/abs/2502.08235. Reasoning models in agent loops reason instead of
  acting, and resolve fewer issues as they do. My agent's decisions that ran out of room are the
  extreme case. Its remedy, several low-effort tries and the best one, keeps reasoning on.
- Wang et al., "Thoughts Are All Over the Place: On the Underthinking of o1-Like LLMs", 2025.
  https://arxiv.org/abs/2501.18585. Reasoning that switches paths too often without finishing one; the
  rewrite decision that counted words, tightened and counted again looked like this.
- Shen et al., "Thinking vs. Doing: Agents that Reason by Scaling Test-Time Interaction", 2025.
  https://arxiv.org/abs/2506.07976. For agents, more steps can beat longer reasoning per step.

**Repetition in agent loops**

- Hou et al., "When Agents Do Not Stop: Uncovering Infinite Agentic Loops in LLM Agents", arXiv
  2607.01641. https://arxiv.org/abs/2607.01641. Loops arise where a feedback path has no effective
  bound; 68 confirmed in 47 open repositories. My 14-call cap is that bound in the experiment.
- Zhang et al., "MIRAGE-Bench: LLM Agent is Hallucinating and Where to Find Them", 2025.
  https://arxiv.org/abs/2507.21017. Actions unfaithful to the execution history, which includes acting
  as if a failed step had worked.

None of these compares turning reasoning off for one decision with turning it off for the rest of a
turn. Ares comes closest: it changes effort per step, but it chooses each step's effort before the
step runs, and does not handle a step that has already run out.
