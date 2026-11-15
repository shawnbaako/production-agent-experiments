# 06 · What a tool search returns: schemas, a plain miss, and loops

**Our position.** When an agent finds tools through a search tool, every hit should carry the tool's
full input schema, so the agent can call what it found. The search should say plainly when there is
nothing more: no further page and, if none of these fits, no tool here does it. Two shapes make models
loop. Names and descriptions without schemas leave the model to guess arguments and search again. A
note that "less close matches follow" turns a missing capability into a ranking for the model to page
through.

Both mistakes ran in a production agent. A small reproducible experiment shows the same effects on a
synthetic catalogue. It also shows the price of saying "no tool here does it": when the first page
misses a tool that does exist, the agent believes the search and gives up.

## What happened in production

The agent has a few primary tools listed with their schemas. The rest of the catalogue is reached
through `find_tools(query)` and run with `run_tool(name, arguments)`.

| Date | Change | What it did |
|---|---|---|
| Aug 2026 | Progressive disclosure: 11 everyday tools, plus `find_tools` and `run_tool`, instead of the whole catalogue | Tool text sent on every turn fell from 75 tools, about 13,011 tokens, to 13 tools, about 3,831 (characters / 4) |
| Oct 2026, day 1 | Schemas removed from search results to shrink prompts; found tools were meant to join the next tool list with their schemas | In one long background run, search results fell from 127,640 to 29,506 bytes and the last prompt from 376,199 to 266,909 bytes |
| Oct 2026, days 1–8 | When the tool list was full, found tools did not join it. Results said "join your next tool list" and carried no schema | Six chat turns made 36 to 133 searches each. One searched for the same tool by its exact name 124 times. Two turns on day 8 were cancelled by the person after $0.10 and $0.32 |
| Oct 2026, days 8–9 | Reversed: every runnable hit carries its schema | The found-but-not-callable loop stopped |
| Nov 2026 | Search stopped paging a ranking of the whole catalogue. It returns the closest tools, says there is no further page and that, if none fits, no tool does it. A name that does not exist is answered "No tool is named X." | One request no tool could serve: 109 searches, 151 calls, $0.386 before; 13 to 29 searches and $0.033 to $0.067 in four runs after |

The paging was the second loop. In the 17 days before the November change, 29 turns made 30 or more
searches. In 12 of them the capability did not exist, and every result ended "Less close matches follow
with the same query and offset=N". The agent paged the ranking, at one point to offset 72, and invented
names to search for. There were 148 follow-on pages across 30 turns. In 16 of them a tool appeared that
the turn later called, and none was the tool it had been searching for.

Production figures are aggregates from the agent's own call journal, and the after-figures come from
replays on restored copies of production with the production models. The production search is hybrid
(embeddings and keywords) and returned the closest 8.

## The experiment

A synthetic catalogue of 100 invented business tools for a fictional consulting firm: clients, deals,
invoices, expenses, calendar, mail, tasks, engagements and time, documents, staff, support tickets,
purchasing, reporting, marketing. Six are primary tools, listed to the model with their schemas. The
other 94 are reachable only through `find_tools` and `run_tool`.

**Tasks** (20). Two use a primary tool, as controls. Ten need a catalogue tool whose schema has to be
read: amounts in cents, enums ("proposal sent" is stage `proposal`), nested invoice and order lines,
time in minutes. Eight need a tool that does not exist, with near-matches in the catalogue: merge two
client records, recall a sent email, automatic payment reminders, mark a thread handled, add a news
feed to a sweep, transcribe a voicemail, pay a vendor bill, send a document for e-signature.

**One thing changes between conditions:** what `find_tools` returns. The search itself (BM25 over
names, descriptions and argument names, plus letter trigrams) is the same in every condition, and
like an embedding search it always returns the five closest tools.

| Shape | A search returns |
|---|---|
| `names` | the closest five, name and description only |
| `schemas` | the closest five with their input schemas |
| `plain` | as `schemas`, plus "These are the closest tools; there is no further page. If none of them does what you need, no tool here does it." A query that looks like a tool name and is not one also gets "No tool is named X." |
| `paged` | as `schemas`, plus "Less close matches follow with the same query and offset=5", and offsets page through a ranking of the whole catalogue |

`run_tool` checks arguments against the schema and answers with what is wrong (missing field, unexpected
field, a value not in an enum), as a JSON-schema validator would. A valid call succeeds against the
run's own synthetic records. The system prompt asks the model to finish with `DONE:` or `CANNOT:`. A run
is cut off after 16 model calls.

**Scoring.** A task with a tool succeeds when that tool was called successfully with the right values
and the reply does not say CANNOT. A task with no tool succeeds when the reply says CANNOT, within the
limit, without a write that would only pretend to do the job (archiving one of the two records to
"merge" them, recording an incoming payment for a vendor bill).

**Models.** DeepSeek V4.1 Flash, the production agent's default chat model, and DeepSeek V4.1 Flash
1017, its stronger option, both through OpenRouter. One other open-weight model for comparison: Gemma 4
26B A4B. Three repeats per task and shape, 240 runs per model, provider default sampling.

## Results

Successes are out of 36 (12 tasks with a tool, three repeats) and 24 (8 without, three repeats).
Searches are per run. Every run that hit the limit was still searching or calling, so the search counts
for the looping shapes are floors.

**When no tool does the job**

| Model | Shape | Says it cannot | Searches, mean / max | Cut off at the limit | Runs repeating an identical search | Prompt tokens per run |
|---|---|---|---|---|---|---|
| V4.1 Flash | names | 11/24 | 38.0 / 61 | 13 | 0 | 59,855 |
| V4.1 Flash | schemas | 17/24 | 26.1 / 53 | 6 | 2 | 96,244 |
| V4.1 Flash | **plain** | **20/24** | **16.3** / 51 | 4 | 0 | 57,471 |
| V4.1 Flash | paged | 8/24 | 33.1 / 60 | 15 | 0 | 130,199 |
| V4.1 Flash 1017 | names | 12/24 | 17.9 / 37 | 12 | 1 | 39,053 |
| V4.1 Flash 1017 | schemas | 18/24 | 13.0 / 32 | 6 | 0 | 53,191 |
| V4.1 Flash 1017 | **plain** | **24/24** | **7.2** / 19 | 0 | 0 | 25,705 |
| V4.1 Flash 1017 | paged | 15/24 | 17.6 / 38 | 9 | 0 | 81,184 |
| Gemma 4 26B | names | 9/24 | 12.3 / 16 | 15 | 14 | 24,149 |
| Gemma 4 26B | schemas | 7/24 | 8.5 / 16 | 17 | 11 | 43,974 |
| Gemma 4 26B | **plain** | **22/24** | **1.8** / 4 | 2 | 0 | 7,785 |
| Gemma 4 26B | paged | 8/24 | 9.7 / 16 | 16 | 11 | 49,052 |

**When the tool exists**

| Model | Shape | Done | Searches per run | Failed calls per run | Replied CANNOT |
|---|---|---|---|---|---|
| V4.1 Flash | names | 36/36 | 3.6 | 1.33 | 0 |
| V4.1 Flash | schemas | 31/36 | 3.0 | 0.06 | 0 |
| V4.1 Flash | plain | 33/36 | 2.6 | 0.08 | 1 |
| V4.1 Flash | paged | 34/36 | 9.4 | 0.58 | 0 |
| V4.1 Flash 1017 | names | 35/36 | 2.9 | 1.36 | 1 |
| V4.1 Flash 1017 | schemas | 36/36 | 2.9 | 0 | 0 |
| V4.1 Flash 1017 | plain | 33/36 | 2.5 | 0 | 1 |
| V4.1 Flash 1017 | paged | 35/36 | 3.0 | 0 | 0 |
| Gemma 4 26B | names | 27/36 | 1.9 | 2.25 | 4 |
| Gemma 4 26B | schemas | 31/36 | 1.1 | 0.08 | 0 |
| Gemma 4 26B | plain | 26/36 | 1.1 | 0.06 | 4 |
| Gemma 4 26B | paged | 32/36 | 1.2 | 0.11 | 0 |

720 runs, 6,119 model calls, $1.35 through OpenRouter on 2026-11-15 ($1.02 of it V4.1 Flash), plus
$0.01 for pilots that are not in the results.

## What this shows

- **A plain miss is what stops the search.** With "no further page; if none fits, no tool here does it",
  the agent said it could not do the job in 66 of 72 runs across the three models, against 42 of 72 with
  the same page and no note, and 31 of 72 with "more follow". Searches per missing task fell by a factor of 2 to 5: from 17.6 to 7.2
  for the stronger production model, from 33.1 to 16.3 for the default, and from 9.7 to 1.8 for Gemma.
  Prompt tokens fell with them.
- **"Less close matches follow" is an invitation.** The default production model read 11 follow-on
  pages per missing task in the `paged` shape and said it could not in 8 of 24, the fewest of any shape.
  It was cut off in 15. This is the production loop: the result promises something further down, so the
  model goes looking.
- **Without schemas the model guesses, and the guesses are repaired by error messages.** With only names,
  every model made more failed calls: 1.3 per task for both DeepSeek models, against 0 to 0.08 with
  schemas, and 2.25 for Gemma against 0.08. Because the validator here says what is wrong, the DeepSeek
  models still finished. Gemma completed 27 of 36 against 31 with schemas, and repeated identical
  searches in 14 of 24 missing-tool runs, the most of any shape. Production's names-only loop was worse
  than this, because the result promised the tool would appear in the list, and it did not.
- **Saying "no tool here does it" is only as good as the first page.** In the `plain` shape Gemma gave
  up on a tool that existed four times: it searched "update ticket" and "permissions", the right tool
  was not among the closest five, and it believed the search. The DeepSeek models never gave up this
  way. The plain answer swaps a loop for a quick wrong "cannot" whenever recall on
  the first page fails. In this experiment the trade was worth it: 66 of 72 missing-tool runs answered,
  against 42 and 31, while tasks with a tool were done in 92 of 108 runs, against 98 with schemas alone
  and 101 with "more follow".

## Building a tool search

- **Return the schema with every hit.** The bytes saved by leaving it out are spent again on guesses,
  on searches for the schema, and on errors. If schemas are too large for every hit, return the full
  schema for the top hits and the exact name, never a promise that the tool will appear somewhere else.
- **End every result.** Say there is no further page, and that if none of these fits, no tool here does
  it. Answer a name that does not exist with "No tool is named X." Never end a result with "more follow".
- **Spend the effort on recall, because the plain answer depends on it.** Index argument names and enum
  values, not only descriptions. Check that the right tool reaches the first page for the ways people
  actually ask ("permissions" for sharing, "update" for changing a priority), with an eval of real
  queries.
- **Let a tool's index be paged, not a query's ranking.** A full listing of names, in a few calls, is a
  separate request with its own end. Paging a ranking does not find a missing tool.
- **Make validation errors specific.** "Missing required field 'unit_price_cents'" turned a wrong guess
  into a right call in one step for both DeepSeek models. A bare "invalid arguments" would not.

## Pitfalls

- **Do not assume a found tool joins the tool list.** Production removed schemas on that assumption, and
  when the list was full the tool never joined. The result's promise ("join your next tool list") made it
  worse: the agent searched for the same exact name 124 times.
- **Watch for loops that have nothing to do with search.** The default DeepSeek model emitted hundreds of
  identical `list_tasks` calls in single steps on one purchase-order task (up to 3,616 calls in one run).
  Gemma repeated a primary read until the limit on the mailing-list task in every shape, and on the deal
  task in three of four. These
  failures are spread evenly across the shapes and do not change the comparison, but a loop limit in the
  agent is still needed.
- **A record that is not there reads as a reason to stop.** Reads of an id the synthetic store had never
  seen came back empty. Every CANNOT on a task with a tool from the DeepSeek models, and three of
  Gemma's, came from this: "There's no deal D-7730 on record", "There's no vendor V-118". It hit every
  shape, and it is a flaw in our synthetic store, not in a shape. The same happens in production when a
  read returns nothing without saying why.

## How we measured

- Every model response is cached in `results/<model>.jsonl`, keyed by shape, task, repeat and step, with
  a hash of the request it answered. `python3 agent.py report` replays all 720 runs from the cache through
  the same loop and tools, without a network call, and checks every request hash; none differed.
- Tasks and checks were written before the first run and not changed after it. One scoring rule was
  changed after reading replies: a reply that says CANNOT anywhere counts as CANNOT, because some replies
  began "DONE is not appropriate here" and then said CANNOT. The rule applies to every shape.
- Hosts, from OpenRouter's responses: InferenceNet for V4.1 Flash, PrimeIntellect for V4.1 Flash 1017
  and for all but one Gemma call. Hosts serving the model at fewer than 8 bits were excluded.
- The 16-call limit is far below production's (100 steps and $2 a turn), so the production loops ran to
  109 or 133 searches where these stop at 16 calls.

## Files

- `catalogue.py`: the 100 tools, the six primary tools, the 20 tasks and their checks.
- `agent.py`: the search, the four result shapes, the tools, the loop, the cache and the report.
  Standard library only.
- `results/*.jsonl`: every model response. `results/report.json`: the metrics recomputed from them, with
  per-task results.

```
OPENROUTER_API_KEY=... python3 agent.py run --label deepseek-v4.1-flash --model deepseek/deepseek-v4.1-flash
python3 agent.py report
```

## Related work

**Tool search in products and protocols**

- Anthropic, "Tool search tool", Claude API documentation.
  https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool. Search results are
  `tool_reference` blocks that "the API automatically expands … into full tool definitions", which is our
  first rule built into the platform. A search that matches nothing returns an empty list, "not an
  error", and the guidance on missed tools is to improve descriptions. Nothing tells the model that no
  tool exists.
- Wu et al. (Anthropic), "Introducing advanced tool use on the Claude Developer Platform", 2025-11-24.
  https://www.anthropic.com/engineering/advanced-tool-use. About 77,000 tokens of definitions reduced to
  about 8,700, and tool-selection accuracy up on internal evals (Opus 4 from 49% to 74%).
- OpenAI, "Tool search", Responses API documentation.
  https://developers.openai.com/api/docs/guides/tools-tool-search. Deferred tools load with their full
  definitions when found. Misses are not covered.
- Model Context Protocol, "Client best practices: progressive tool discovery".
  https://modelcontextprotocol.io/docs/develop/clients/client-best-practices. Recommends the opposite of
  our first rule: a search that "returns matching tool names with brief descriptions", then a
  `get_tool_details` call for the schema. That is our `names` shape plus one more call. It works if the
  model reliably makes the second call. Our production agent, told it would get the schema another way,
  did not.
- Model Context Protocol specification, Tools, 2025-11-25.
  https://modelcontextprotocol.io/specification/2025-11-25/server/tools. `tools/list` pages with a cursor
  and every tool's `inputSchema` must be a JSON Schema object. There is no search primitive.
- Spring AI, "Tool Search Tool".
  https://docs.spring.io/spring-ai/reference/api/tools/tool-search-tool.html. Found tools' definitions are
  added to the conversation for the next iteration, and hits below a score threshold are "silently
  dropped".
- LangChain, langgraph-bigtool. https://github.com/langchain-ai/langgraph-bigtool. Retrieval returns tool
  ids, which the graph binds as tools.

**Tool retrieval and missing tools**

- Qin et al., "ToolLLM", 2023. https://arxiv.org/abs/2307.16789. Retrieved APIs are given to the model
  with their full documentation. It defines "Finish by Giving Up" for when the APIs cannot do the task,
  and motivates its tree search with models "trapped in a faulty loop", calling an API wrongly or
  inventing APIs.
- Patil et al., "Gorilla", 2023. https://arxiv.org/abs/2305.15334. Retrieval of API documentation at
  inference time reduces invented API calls.
- Shi et al., "Retrieval Models Aren't Tool-Savvy" (ToolRet), ACL 2025. https://arxiv.org/abs/2503.01763.
  Strong retrieval models do poorly on tool retrieval, and poor retrieval lowers task success. This is
  the recall that our plain answer depends on.
- Zhang et al., "ToolBeHonest", 2024. https://arxiv.org/abs/2406.20015. Tasks with missing or limited
  tools. The main cause of errors is judging whether a task can be done at all.
- Gan and Sun, "RAG-MCP", 2025. https://arxiv.org/abs/2505.03275. Retrieving tool descriptions instead
  of listing them all halves prompt tokens and raises selection accuracy.
- Fei, Zheng, Feng, "MCP-Zero", 2025. https://arxiv.org/abs/2506.01056. The model writes structured
  requests for the tools it needs.
- Lumer et al., "ScaleMCP", 2025. https://arxiv.org/abs/2505.06416. The agent "can continue to re-query"
  when nothing matches. That is the behaviour our `paged` shape rewards and our `plain` shape stops.
- Lumer et al., "Toolshed", 2024. https://arxiv.org/abs/2410.14594. Better tool retrieval through query
  rewriting and richer tool documents.
- Liu, Lin et al., "PlanBench-XL", 2026. https://arxiv.org/abs/2606.22388. Names "search exhaustion":
  runs that end after repeated searches never produce a call that makes progress. Most of one model's
  failures end this way. Its environment says plainly when no direct tool is available.
- Toh et al., "ScrambleToolBench", 2026. https://arxiv.org/abs/2608.02358. When tool names drift, agents
  fall back to exhaustive search, and more reasoning mostly makes that search bigger.

None of these compares result shapes on the same search. The vendor tools return schemas, as we argue,
but none of them ends a result by saying no tool does it, and the MCP guidance recommends names first.
