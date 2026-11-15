# Production agent experiments

Experiments from building and running an LLM agent in production: what was tried, what the numbers
were, what was kept and what was removed. Each study answers a question that came up in real work,
with the code and per-item results needed to check it.

## Studies

| # | Study | What it argues | Kind |
|---|---|---|---|
| 01 | [Decision models as a set-reading tool](studies/01-decision-model-set-filter/) | Give the agent a set-filter tool: one yes-no question per item, answered by a decision model. Jev, Clef, Laya, embeddings, BM25 and keyword search on the same 2,900 items | Reproducible |
| 02 | [Proofs, not tests: verifying software that coding agents write](studies/02-proofs-not-tests/) | Unit tests and hosted CI were built for human teams. With coding agents, prove every change on the real seam instead: replays on restored production copies, real services, a browser, outcome evals, and CI on the machine that can see production | Design position, with production data |
| 03 | [Where a decision model belongs in an agent](studies/03-where-a-decision-model-belongs/) | A decision model belongs in the agent's hands as a tool; nine placements in a production agent, and why only that one survived | Design position, with production data |
| 04 | [What the checker sees](studies/04-what-the-checker-sees/) | A sentence checker given only the cited sources flags almost every true sentence taken from other records. Given everything the agent read, the false flags disappear and the errors are still caught | Reproducible |
| 05 | [One agent loop](studies/05-one-agent-loop/) | Why we replaced sub-agents and specialised background agents with one loop, one context and one set of permissions, and what it did to duplicate work, cost and coherence | Design position, with production data |

Related, in its own repository: [Tool calls, stop tokens and missing issue text: Gemma 4 as a coding agent](https://github.com/shawnbaako/gemma4-agent-failure-analysis).

## Hardware notes

- [Tesla P40 speed against temperature](hardware/p40-thermals/): ten weeks of clock, power and request timings from one P40 serving a 27B model at 125 W, with the watchdog and idle downclock that kept it running.

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
