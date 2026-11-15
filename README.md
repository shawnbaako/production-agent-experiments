# Production agent experiments

Experiments from building and running an LLM agent in production: what was tried, what the numbers
were, what was kept and what was removed. Each study answers a question that came up in real work,
with the code and per-item results needed to check it.

## Studies

| # | Study | Question | Status |
|---|---|---|---|
| 01 | [Decision models as a set-reading tool](studies/01-decision-model-set-filter/) | Can one yes-no question per item, answered by a small decision model, find the few relevant items in a set of 1,500? How do Jev, Laya, a local LLM and keyword search compare on the same items? | Results in; local LLM and harder items to come |
| 02 | [Deleting the test suite: proofs on real seams instead of tests](studies/02-deleting-the-test-suite/) | A product built by coding agents deleted 895 test files and banned new ones. What changed, what did it cost, and what does the evidence say against it? | Draft case report |
| 03 | [Where a decision model belongs in an agent](studies/03-where-a-decision-model-belongs/) | A decision model was tried in nine places in a production agent and kept in one. What decided each removal? | Case report |
| 05 | [One agent for chat and background work](studies/05-one-agent-for-chat-and-background/) | A production agent with separate chat and background agents was consolidated into one. What happened to reliability, correctness and cost, and how much is down to the architecture? | Case report |

Related, in its own repository: [Tool calls, stop tokens and missing issue text: Gemma 4 as a coding agent](https://github.com/shawnbaako/gemma4-agent-failure-analysis).

## What a study here contains

- **A question and a result**, stated first, including results that came out null or against expectation.
- **Data anyone can use.** Synthetic or public data only. No private or client data, and no outputs derived from it.
- **Code that reruns it.** Every model answer is cached and committed, so the report can be recomputed without paying for a single call.
- **The simple baseline.** Keyword search, BM25, a linear model on embeddings, or whatever the cheap alternative is.
- **What it does not show.** Sample sizes, single runs, label provenance and anything left unmeasured.
- **Related work.** Prior work the study builds on or replicates, with links that were opened and read.

Some studies began as measurements on a private production system. Where a number comes from that system and cannot be reproduced from this repository, the study says so and gives the sample size.

## Licence

Code is under the Apache License 2.0 (see `LICENSE`). Text, figures and data are under CC BY 4.0.
