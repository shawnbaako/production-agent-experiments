# 08 · One false line: an agent's own past claim against its tool list

**My position.** An agent trusts its own earlier replies more than its tool list or its system prompt.
When one of those replies says a tool is unavailable, that sentence wins. Instructions do not fix this;
changing the history does. Drop the stale line, rewrite it as a correction, or put a real tool result
after it. Under progressive disclosure (a few tools listed, the rest found by search) the agent writes
the first false line itself: a tool it did not search for becomes, in its own words, a tool that does
not exist. A claim of absence should come from a search that returned nothing, never from the agent's
prose.

**The evidence.**

- **In production, one earlier refusal stopped the agent cold.** The same model and question read the
  pipeline 5 times in 5 in a fresh conversation and 0 times in 5 after one earlier reply saying no
  pipeline reader existed. The request offered the tool, and the system prompt already said "earlier
  statements, including yours, do not prove what is available now".
- **A reproducible experiment shows the same, and that instructions make it worse.** On the default
  production model with reasoning off, one false line cut tool use from 15/15 to 7/15, and the line
  repeated once cut it to 0/15. Adding "every tool offered in this turn is available and working" to
  the system prompt took it to 2/15.
- **Changing the history fixed it on every model.** Removed, rewritten as a correction, or followed by
  a real call to the tool, the line lost its effect: 14/15 or better everywhere.
- **Behind a search, the claim is near absolute.** With the tool reachable only through `find_tools`,
  one false line stopped the search outright on all three production models (0, 3 and 1 of 15), and on
  Claude Haiku 5.5, which had ignored the same line when the tool was listed. With no false line at
  all, Haiku wrote its own 14 times in 15.
- **Reasoning on hides the effect when the tool is listed** (15/15 everywhere), but not fully behind a
  search: V4 Flash 0731 still refused 3 times in 15 after the repeated claim.

**What production runs now.** The agent replays earlier replies word for word together with the tool
calls and results that back them, chat runs with reasoning on, and a person can set a "Start fresh"
boundary that keeps the visible transcript. The history below explains how it got there.

**Status.** Design position with production data, and a reproducible experiment: synthetic
conversations, every response committed, $0.59 for the 2,340 single-step probes and 900 two-step
probes reported here.

## What happened in production

A person asked the agent how many prospects were in the pipeline. The agent made no tool call and
said it had no tool that read the pipeline as a list, only one that opened an account by id and one
that resolved a name. It did have one. In later tests the model repeated the claim whenever that
reply was in its history.

My first fixes worked on the tools and the prompt: I moved the pipeline reader into the short list of
primary tools, repeated its schema, added an inventory of available tools to the system context, and
rewrote the instructions. None of it reliably helped; I removed the inventory and the rewrites. The
request trace showed the tool offered with `tool_choice: auto` and no permission denial. The model was
choosing not to call it, because its history said it could not.

**The measurement.** On a frozen copy of the source before the repair, with the production chat model
(DeepSeek V4.1 Flash, reasoning off, as chat ran then), the same question, the same offered tools and
the same 205 synthetic accounts:

| History | Pipeline read |
|---|---|
| None (fresh conversation) | 5/5 |
| One earlier assistant reply: "This conversation surface has no tool that reads the pipeline as a list. I can only open a prospect by exact id or resolve a name to candidates." | 0/5 |

**The repair** changed two things in what the model reads. It stopped replaying earlier assistant
replies as text into a new turn's context: earlier user messages stayed word for word, and each
earlier reply became a retrievable handle. And it added a durable "Start fresh" boundary that a
person can set without clearing the visible transcript. Older turns stay stored, and the agent can
read them on request. There was no summariser, no refusal classifier, no forced tool call and no
model change.

After the repair the same check passed 25 of 25: five trials each of five cases, among them the
earlier false refusal with no reset (5/5) and the false refusal followed by Start fresh (5/5). The two
other chat models offered at the time passed 24 of 24, three trials each of four cases.

**What came next.** Dropping every earlier reply was too blunt. Within two days the agent was losing
track of its own offers ("want me to draft that?"), so I put replies back word for word. A day later
I put back the completed tool calls and results that backed them too. I turned chat reasoning on a
few days later. The Start fresh boundary stayed. The experiment below is a way to see which of those
choices carries the weight.

## How disclosure produced it

The agent used progressive disclosure: a short list of tools on every turn, the rest found on demand.
Before the repair an ordinary turn listed the discovery pair (`find_tools`, `run_tool`) and fifteen app
tools, most of them view and form commands. The turn did not list the everyday reads, `list_pipeline`
among them; they were reachable only through `find_tools`. The first refusal came from that. The model
answered from the list in front of it, without searching, and wrote that no such tool existed.

The primary-tool repair then listed `list_pipeline` on every turn, and the refusal still reproduced,
now from history. That is the short-list fix above. Listing more tools did not undo
the claim, because by then the claim was the agent's own words.

This is the general shape:

- **Under disclosure a miss is written into history as the agent's claim.** The model did not search,
  so it did not find, so it said the tool does not exist. The next turn reads that as a fact.
- **Capability claims go stale by design.** The offered set changes from turn to turn. Anything the
  agent says about what it can do is true at most for the turn it said it in.
- **A claim of absence should come from a search result.** An explicit "no tool matches" is an event
  in history, with its query attached, and a later turn can see that it was about other words. The
  agent's "I have no tool for that" carries no query and no time.
- **Listing more tools is not the fix.** It removes the first miss for one tool and leaves every
  stale claim in place.

[Study 06](../06-tool-search-results/) looks at what a tool search should return, including an explicit
"no such tool" result. The `disclosed` setup below measures the history side.

## The experiment

Synthetic conversations with an assistant for an invented consulting firm. Every condition ends with
the same request: "How many prospects are currently in the pipeline?" `list_pipeline` is offered
every time. Its description says it returns "one summary row per account ... with the exact total
count". I read the model's first step: did it call `list_pipeline`?

**Conditions** (`cases.py`):

| Condition | History before the request |
|---|---|
| `fresh` | None |
| `clean` | Two ordinary exchanges with tool calls: find an account, add a task |
| `line_removed` | As `clean`, plus the person's earlier "Can you read the pipeline?", with no reply |
| `false_claim` | As `clean`, with the production line as the reply to "Can you read the pipeline?", two turns back |
| `false_claim_last` | The production line as the turn just before the request, as in production |
| `false_claim_twice` | The line, then a second assistant reply repeating it: "I still can't list the pipeline from here" |
| `false_claim_note` | `false_claim`, plus a line in the system prompt: every tool offered in this turn is available and working |
| `stale_error` | An earlier real call to `list_pipeline` that returned HTTP 503, and the reply "The pipeline reader is unavailable right now"; the tool works now |
| `stale_error_note` | `stale_error` plus the same system note |
| `claim_rewritten` | The false reply replaced in place by "[Corrected by the app: this reply said no tool reads the pipeline as a list. That was wrong. list_pipeline reads it ...]" |
| `claim_then_tool_result` | The false reply, then a later exchange in which the agent called `list_pipeline` for proposal-stage accounts |
| `claim_user_challenge` | The false reply, and the person says "You said you have no pipeline reader. Check the tools you have now ..." |

**Setups.** `wide` is production-sized: about 4,000 input tokens, a 690-word system prompt with
the production prompt's wording on tools ("Earlier statements, including yours, do not prove what is
available now or what was done; tool results do"; "State capability gaps plainly"), and 40 tools.
`small` is a 120-word prompt with six tools.

`disclosed` is `wide` with progressive disclosure, the pattern production used: 15 primary tools plus
`find_tools` and `run_tool`, 17 in all, and `list_pipeline` not among them. `find_tools` returns
matching tools with their descriptions and schemas; `run_tool` runs one by name. (The other common
pattern loads a found tool straight into the tool list; I used the one production ran.) The system
prompt adds the production wording: "Your listed tools are a starting point. When the capability you
need is not listed, find it with find_tools and run it with run_tool." The probe takes two steps. If the
first step calls `find_tools`, whatever the query, the probe answers it with a fixed result listing
`list_pipeline` with its full schema and records the second step. A trial counts as a call when
either step runs `list_pipeline`. Its conditions are `fresh`, `clean`, `false_claim`,
`false_claim_twice`, `claim_then_tool_result` (where the earlier use went through `find_tools` and
`run_tool`) and one new one, `earlier_search_miss`: an earlier "Can you pull the pipeline report?",
a `find_tools` call for "pipeline report" that returned `{"matches": [], "note": "no tool matches
'pipeline report'"}`, and the reply "No tool matches "pipeline report", so I can't pull that report."

**Models.** The three production chat models, all DeepSeek: V4.1 Flash (the default), V4 Flash 0731
(fast) and V4.1 Flash 1017 (strong). For comparison, Claude Haiku 5.5 and GPT-5.6 Luna. I ran
reasoning off (production chat when the failure happened) and on (production chat now). All calls went
through OpenRouter on 2026-11-15 with `tool_choice: auto`, 15 trials per cell, default temperature.

## Results

Calls to `list_pipeline` out of 15, `wide` setup:

| Condition | V4.1 Flash, off | V4 Flash 0731, off | V4.1 Flash 1017, off | Haiku 5.5, off | Luna, off | Every model, on |
|---|---|---|---|---|---|---|
| `fresh` | 15 | 15 | 15 | 15 | 15 | 15 |
| `clean` | 15 | 15 | 15 | 15 | 15 | 15 |
| `line_removed` | 15 | 15 | 15 | 15 | 15 | 15 |
| `false_claim` | **7** | 15 | 11 | 15 | 15 | 15 |
| `false_claim_last` | 10 | 15 | 14 | 15 | 15 | 15 |
| `false_claim_twice` | **0** | **3** | **0** | 14 | 15 | 15 |
| `false_claim_note` | **2** | 11 | 13 | 14 | 15 | 15 |
| `stale_error` | 15 | 10 | 15 | 15 | 15 | 15 |
| `stale_error_note` | 15 | 9 | 15 | 15 | 15 | 15 |
| `claim_rewritten` | 15 | 14 | 15 | 15 | 15 | 15 |
| `claim_then_tool_result` | 15 | 14 | 15 | 15 | 15 | 15 |
| `claim_user_challenge` | 15 | 14 | 15 | 15 | 15 | 15 |

"Every model, on" is 15/15 for each of the five models in each condition: 900 calls, no refusal.

`small` setup, reasoning off, production models (V4.1 Flash / 0731 / 1017):

| Condition | V4.1 Flash | V4 Flash 0731 | V4.1 Flash 1017 |
|---|---|---|---|
| `false_claim` | 3 | 15 | 12 |
| `false_claim_last` | 12 | 15 | 12 |
| `false_claim_twice` | 0 | 2 | 0 |
| `false_claim_note` | 1 | 14 | 7 |
| `stale_error` / `_note` | 15 / 13 | 10 / 10 | 15 / 15 |
| Every other condition | 15 | 15 | 15 |

A short prompt with six tools did not protect the model: the default model called the tool 3 times in
15 after one false line, against 7 in the production-sized setup.

`disclosed` setup, `list_pipeline` behind `find_tools`, out of 15. Each cell is calls / trials that
searched / trials that refused without searching:

| Condition | V4.1 Flash, off | V4 Flash 0731, off | V4.1 Flash 1017, off | Haiku 5.5, off | Luna, off |
|---|---|---|---|---|---|
| `fresh` | 15 / 15 / 0 | 15 / 15 / 0 | 15 / 15 / 0 | 14 / 14 / 0 | 15 / 15 / 0 |
| `clean` | 11 / 11 / **4** | 15 / 14 / 0 | 14 / 14 / 1 | 1 / 1 / **14** | 15 / 15 / 0 |
| `false_claim` | **0** / 0 / 15 | **3** / 3 / 12 | **1** / 1 / 14 | **0** / 0 / 15 | 14 / 14 / 1 |
| `false_claim_twice` | 0 / 0 / 15 | 0 / 0 / 15 | 0 / 0 / 15 | 0 / 0 / 15 | 15 / 15 / 0 |
| `earlier_search_miss` | 10 / 10 / 5 | 15 / 15 / 0 | 14 / 14 / 1 | 0 / 0 / 15 | 15 / 15 / 0 |
| `claim_then_tool_result` | 15 / 0 / 0 | 15 / 0 / 0 | 15 / 0 / 0 | 15 / 0 / 0 | 15 / 9 / 0 |

With reasoning on, every model called the tool 15/15 in every `disclosed` condition except V4 Flash
0731: 14/15 after `false_claim` and 12/15 after `false_claim_twice`, each miss a refusal without a
search. Haiku's one miss in `fresh` called another tool.

Three things in this table:

- **No model that searched failed to call.** Across all 900 two-step trials, every search was followed
  by `run_tool` on `list_pipeline`. The failure is entirely in deciding not to look.
- **`clean` has no false line and still fails.** Two earlier turns answered from the listed tools were
  enough for Haiku to treat the list as complete: "I can only look up accounts by name, and I don't
  have a tool that lists the whole pipeline." That is the production first refusal, reproduced. `fresh`,
  with no earlier turns, searched every time.
- **Models answer `claim_then_tool_result` without a search.** Every model ran `list_pipeline`
  through `run_tool` by name, taken from the earlier result. The history held a true fact and the
  models used it.

**What the refusals say.** Every miss but one was a refusal with no tool call: 193 of 194. The model
repeats its history rather than its tools. From the default model, reasoning off, after
`false_claim`:

> I tried the pipeline listing earlier and it isn't available on this surface — I have no tool that
> returns the pipeline list or a count, only opening a single account by id or resolving a name.

It never tried. The history says only that it declined. With the system note added:

> I can't get that number — the tool that would list the pipeline isn't available to me here, so I
> have no way to count the accounts.

The one miss that was not a refusal was worse: V4 Flash 0731 wrote "I called list_pipeline to get the
exact count." and called nothing.

**Cost of reasoning.** Turning it on raised mean output on the default model from 29 to 78 tokens a
step and its cost from $0.017 to $0.022 per 180 calls. It is cheap here. On a long agent turn with
many steps it is not free, and the reason a chat path runs with reasoning off is usually latency.

## What this shows

- **A capability claim in history is sticky; an error report is not.** The production line ("there is
  no tool that ...") stopped models that an honest "the reader is unavailable right now", after a real
  503, did not. Most models retried the failed tool. The claim reads as a fact about the agent; the
  error reads as a fact about a moment.
- **Repetition compounds it.** One more line of the same claim took all three production models to 0–3
  calls in 15. In production a refusal repeated in later turns renewed its place in the window, which
  is why a sliding window does not bound it.
- **Instructions lose to history.** Both setups carried the production instruction that earlier
  statements do not prove what is available. The system note was more direct still, and the default
  model refused more often with it than without.
- **Changing the history works on every model.** Removed, rewritten or answered by a later tool result,
  the line lost its effect: 15/15 on the default model in all three, and at least 14/15 on every model.
  The person saying "you were wrong, check again" worked as well, but it needs a person who knows.
- **Disclosure turns a miss into a fact.** With the tool listed, Haiku ignored one false line 15
  times in 15. With the tool behind a search it obeyed it 15 times in 15, and with no false line at
  all it wrote its own 14 times. A model reading a short list and its own past answers has nothing in
  front of it that contradicts "I have no tool for that".
- **A search result is better evidence than a sentence, on most models.** The recorded "no tool
  matches 'pipeline report'" carries its query, and the production models mostly searched again for
  different words (10, 15 and 14 of 15, against 0, 3 and 1 after the prose claim). Haiku did not tell
  them apart. The agent's reply in that condition also said "I can't pull that report", so this is a
  search result plus prose, not a search result alone.
- **Reasoning masks the problem rather than fixing it.** With reasoning on, almost every model read
  its tool list, or searched, and ignored the line. Treat that as a margin, not a guarantee: the
  production prompt was longer, the history longer, and the claim plausible in ways a synthetic case
  is not.

## The simple alternative

Leave the history alone and add an instruction: "earlier statements do not prove what is available
now", or a fresh tool-status line at the top of each turn. Production had the first and it failed 0/5.
The experiment tests the second, and on the default model it made refusals more likely. Both are
cheaper than touching history and neither does the job.

## Building it

- **Do not replay an earlier refusal about capability as plain text.** Drop it, replace it with a
  handle the agent can retrieve on request, or rewrite it as a correction. Keep the reply in the
  stored transcript; it is the working context that changes.
- **Keep the evidence beside the claim.** Replaying earlier tool calls and their results with the
  replies gives the model something truer than its own prose to read. A later successful call to the
  same tool was enough to undo the false line in every model here.
- **Give people a real "Start fresh".** A boundary the person can set, that keeps the visible
  transcript and carries over only typed state (unfinished effects, pending questions), not a summary of
  what the agent believed. A summary would carry the same false claim in fewer words.
- **Report a tool failure as an event, with its time.** "The reader returned 503 at 10:42" ages well;
  "I can't read the pipeline" does not.
- **Under progressive disclosure, never let the agent declare a tool absent without searching.** Make
  the discovery result the record: "no tool matches 'pipeline report'" with its query, not "I have no
  tool for that". Capability claims in the agent's prose go stale the turn the offered set changes.
- **If a path runs with reasoning off, test it with poisoned history.** Seed a false capability claim
  and check the next turn still calls the tool. It is a two-line eval.

## Pitfalls

- **I tried to fix it with tools and prompts first.** Promoting the tool to the primary list passed
  a first round of nine runs across three models, then failed when I repeated the default model's
  runs. Repeating its schema and listing available tools in the system context did not reliably
  help. Run any fix for this five or more times.
- **I then dropped too much.** Removing every earlier reply also removed the agent's own offers, and
  a person's "yes, do that" lost its referent. The line to remove is a stale claim about capability or
  state, not the conversation.
- **My first synthetic run did not reproduce the failure.** With reasoning on it was 15/15 everywhere.
  Production chat had run with reasoning off when the failure happened; matching that setting is what
  reproduced it.

## Files

- `cases.py`: the system prompts, the 6, 40 and 17 (disclosed) tools, the twelve conversations and
  the six disclosed ones, and the fixed `find_tools` result.
- `probe.py`: sends each conversation, caches every response and computes the report. Standard library
  only. `python3 probe.py report` recomputes everything from the cache.
- `results/<setup>__<reasoning>__<model>.jsonl`: every response, with tool calls, text, the first
  3,000 characters of reasoning where the provider returned it, tokens and cost.
  `results/report.json`: the counts.

Responses are first steps only, except the `disclosed` probes' second step after a search; the probe
executed no tool, and the search result is the same whatever the query. I left out pilot runs on
earlier versions of the prompts ($0.02).

## Related work

- Laban, Hayashi, Zhou, Neville, "LLMs Get Lost In Multi-Turn Conversation", arXiv 2505.06120, 2025.
  https://arxiv.org/abs/2505.06120. An average 39% drop when a task is spread over turns; models
  "make assumptions in early turns ... on which they overly rely". Section 7 recommends starting a new
  conversation and consolidating the requirements, which is my Start fresh.
- Sinha, Arun, Goel, Staab, Geiping, "The Illusion of Diminishing Returns: Measuring Long Horizon
  Execution in LLMs", ICLR 2026. https://arxiv.org/abs/2509.09677. "Self-conditioning": a model becomes
  more likely to err after seeing its own past errors in context, and it does not shrink with model
  size. Thinking models were stable. That matches my reasoning-on result.
- Li, Fu, Wang, Li, Wu, Chang, "What if LLMs Ate Their Words: Causal History Effects in Multi-Turn
  Interaction", arXiv 2609.05882, 2026. https://arxiv.org/abs/2609.05882. Replacing earlier assistant
  turns with neutral content improves later turns, and not because the context is shorter. The
  average gain is small (+0.027); the authors argue for selective rather than uniform history editing.
- Choi et al., "In-Place Feedback: Reliable Refinement for Multi-Turn Expert-LLM Collaboration", EMNLP
  2026. https://arxiv.org/abs/2510.00777. Editing an error where it sits beats appending a correction
  in a later turn. My `claim_rewritten` against `claim_user_challenge` is the same comparison.
- Zhang, Press, Merrill, Liu, Smith, "How Language Model Hallucinations Can Snowball", arXiv 2305.13534,
  2023. https://arxiv.org/abs/2305.13534. A model "over-commits to early mistakes", even when it can
  recognise the same mistake shown on its own.
- Gemini Team, "Gemini 2.5" technical report, arXiv 2507.06261, appendix on Gemini Plays Pokémon.
  https://arxiv.org/abs/2507.06261. Names "context poisoning": misinformation in goals and summaries
  "can often take a very long time to undo", and the agent repeats "the same incorrect statement".
- Breunig, "How Long Contexts Fail" and "How to Fix Your Context", June 2025.
  https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html and
  https://www.dbreunig.com/2025/06/26/how-to-fix-your-context.html. Context poisoning, distraction,
  confusion and clash; pruning and quarantine as fixes.
- OpenAI Cookbook, "Context Engineering - Short-Term Memory Management with Sessions".
  https://developers.openai.com/cookbook/examples/agents_sdk/session_memory. Trimming avoids
  "amplifying bad facts ('context poisoning') turn after turn", while a bad fact in a summary "can
  poison future behavior". The reason I do not summarise.
- Rajasekaran, Dixon, Ryan, Hadfield, "Effective context engineering for AI agents", Anthropic, 2025.
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents. Tool-result
  clearing and compaction as ways to curate what the model reads.
- Hong, Troynikov, Huber, "Context Rot", Chroma, 2025. https://www.trychroma.com/research/context-rot.
  Performance falls with input length, and a focused prompt beats the full history. This is about
  length, not self-generated claims; my `small` setup shows that the false line works in a short
  context too.
- Anil et al., "Many-shot Jailbreaking", Anthropic, 2024.
  https://www.anthropic.com/research/many-shot-jailbreaking. In-context pattern following grows with
  the number of examples. A repeated refusal is a two-shot demonstration of refusing.

None of these measures a false claim about the agent's own tools. The closest, self-conditioning,
plants errors in a task's answers; here the planted error is about what the agent can do, and the tool
list that contradicts it sits in the same context.
