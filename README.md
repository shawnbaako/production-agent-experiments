# Production agent experiments

Experiments from building and running an LLM agent in production: what was tried, what the numbers
were, what was kept and what was removed. Each study answers a question that came up in real work,
with the code and per-item results needed to check it.

## Studies

| # | Study | What it argues | Kind |
|---|---|---|---|
| 01 | [Decision models as a set-reading tool](studies/01-decision-model-set-filter/) | Give the agent a set-filter tool: one yes-no question per item, answered by a decision model. Jev, Clef, Laya, embeddings, BM25 and keyword search on the same 2,900 items | Reproducible |
| 02 | [Proof on the real seam: integration, end-to-end and evals instead of agent-written tests](studies/02-proof-on-the-real-seam/) | When coding agents write the code, their own tests are a weak, expensive signal. Make "done" mean the change works on the real seam: replays on restored production copies, real services, a browser, outside assistants, readbacks and outcome evals. Ban every new test, not just unit tests, or the habit moves into fake-adapter integration tests. Two production codebases | Design position, with production data |
| 03 | [Where a decision model belongs in an agent](studies/03-where-a-decision-model-belongs/) | A decision model belongs in the agent's hands as a tool; nine placements in a production agent, and why only that one survived | Design position, with production data |
| 04 | [What the checker sees](studies/04-what-the-checker-sees/) | A sentence checker given only the cited sources flags almost every true sentence taken from other records. Given everything the agent read, the false flags disappear and the errors are still caught | Reproducible |
| 05 | [One agent loop](studies/05-one-agent-loop/) | Why we replaced sub-agents and specialised background agents with one loop, one context and one set of permissions, and what it did to duplicate work, cost and coherence | Design position, with production data |
| 06 | [What a tool search returns](studies/06-tool-search-results/) | Return the full schema with every hit and say plainly when nothing more matches; names without schemas and "more matches follow" pages make agents loop. 100 synthetic tools, four result shapes, three models | Reproducible, with production data |
| 07 | [Reasoning off for one decision, not for the turn](studies/07-reasoning-off-per-decision/) | When one decision reasons through all its room, retry that decision with more room and reasoning on. Reasoning off for the rest of the turn gets less done and, in production, repeated refused calls 19 to 29 times | Design position, with production data and a reproducible experiment |
| 08 | [One false line](studies/08-one-false-line/) | An agent's own earlier "that tool is unavailable" outweighs its tool list and system prompt. Under progressive disclosure it is near absolute, and the agent writes the first false line itself; removing, rewriting or following the line with a real tool result fixes it | Reproducible, with production data |
| 09 | [Search engine mix](studies/09-search-engine-mix/) | Choose an agent's metasearch engines by measuring them from your own address, keep three that answer, and don't pass a date filter to general search: SearXNG silently drops engines that can't filter, turning a three-engine search into one engine or none | Reproducible, with production data |
| 10 | [Search ranking for agents](studies/10-search-ranking-for-agents/) | Order search candidates with a decision model asked one question per listing, and pass its top score to the assistant: under 0.5, nothing fully matches. A cross-encoder ranked no better than the multilingual embedding and its scores cannot say "none"; an English-only gate passes an embedding that finds nothing in five scripts. Production pools and a public Wikivoyage replica in 11 languages | Reproducible, with production data |
| 11 | [Checking extracted facts](studies/11-checking-extracted-facts/) | Check facts an agent extracts in two steps: a deterministic number and unit check, then a cheap decision model reading the whole source. A judge shown only the cited excerpt wrongly rejects a quarter to a third of correct facts and lets through half the values copied from another offering; the same model given the whole source rejects a fifth, so the whole source is necessary, not sufficient | Reproducible, with production data |
| 12 | [Workflows versus one agent](studies/12-workflows-vs-agent/) | Fixed workflows match an agent with the same tools only on the cases they were written for; off script they hand back or do harm, each guard fixes one named case, and machinery bolted onto the agent costs it the work. Keep hard code for money, access, the send boundary and mechanical loop stops | Design position, with production data and a reproducible experiment |
| 13 | [Photo facts from the embedding you already have](studies/13-photo-facts/) | Train small heads on the image vectors search already computes, with labels from a strong model checked against people, and gate each answer on a held-out lower bound. Agent labels match people on objects and drift on judgment cues; a $0.70 Qwen3.5-2B fine-tune learns the labeller's definitions and makes a good label miner; small samples make heads and fine-tunes look ready when they aren't. Don't read safety facts from photos | Reproducible, with production data |

Related, in its own repository: [Tool calls, stop tokens and missing issue text: Gemma 4 as a coding agent](https://github.com/shawnbaako/gemma4-agent-failure-analysis).

## Hardware notes

- [Tesla P40 at a 125 W limit](hardware/p40-thermals/): clock, power and temperature over ten weeks; at the power limit heat costs about 13% of clock by 80 °C, and an idle downclock keeps the card at 31 °C instead of 60 °C.

## What a study here contains

- **Our position first.** What we think builders should do, and the result that backs it.
- **Real numbers.** From a production agent, or from a reproducible experiment with the code, the data
  and every model answer committed, so the numbers can be recomputed without paying for a call.
- **The simple alternative.** Keyword search, BM25, a rule, a default: whatever a builder would try first.
- **Pitfalls.** The mistakes we made, so others can skip them.
- **Related work.** Who said it before, who disagrees, with links that were opened and read.

Reproducible experiments use synthetic or public data only. Production figures are aggregates.

## Licence

Code is under the Apache License 2.0 (see `LICENSE`). Text, figures and data are under CC BY 4.0.
