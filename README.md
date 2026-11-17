# Production agent experiments

Positions on how to build LLM agents, each backed by what happened when we ran one in production. Every
study states what we think builders should do, shows the production numbers that led us there and,
where it can, a reproducible experiment with the code, the data and every model answer committed, so
anyone can check the numbers without paying for a call.

## What we believe

The thirteen studies come down to nine convictions.

1. **The agent decides. Code holds only what must be exact.** One agent loop with the person's whole
   context does the work. Hard code is for money arithmetic, access, the outward boundary (sending,
   publishing, paying) and mechanical stops that judge nothing. Workflows, routers, guards and
   specialised sub-agents each decide without the full picture, and cost more than they save.
   [03](studies/03-where-a-decision-model-belongs/), [05](studies/05-one-agent-loop/),
   [12](studies/12-workflows-vs-agent/)
2. **Done means it works on the real system.** When the same agent writes the code and the tests, the
   tests agree with the code by construction, bugs included. Ban agent-written tests outright, and prove
   each change on a restored copy of production, the real services and a browser.
   [02](studies/02-proof-on-the-real-seam/)
3. **A checker must see what the writer saw.** Shown only the cited sources, a checker flags true
   sentences, and a judge shown only an excerpt passes a value copied from the wrong item. Give it
   everything the agent read. [04](studies/04-what-the-checker-sees/),
   [11](studies/11-checking-extracted-facts/)
4. **List the tools the agent needs, and make search tell the truth.** A tool reachable only through
   search went unused. Every search hit needs its schema, and every search result must say plainly when
   nothing more exists. [01](studies/01-decision-model-set-filter/),
   [06](studies/06-tool-search-results/)
5. **An agent believes its own history over its instructions.** One stale "that tool is unavailable"
   outweighs the tool list and the system prompt. Fix the history, not the prompt.
   [08](studies/08-one-false-line/)
6. **Rank, don't cut, and say when nothing fits.** Give the agent a decision model's ranking and
   probabilities rather than a fixed threshold, and pass the top score on as a fact the agent can use to
   say "nothing matches". [01](studies/01-decision-model-set-filter/),
   [10](studies/10-search-ranking-for-agents/)
7. **Reasoning belongs to a decision, not a turn.** Retry the one decision that ran out of output budget
   with a bigger budget. Never switch reasoning off for the rest of the turn.
   [07](studies/07-reasoning-off-per-decision/)
8. **Measure under your own conditions.** Search engines behave differently from your address,
   embeddings differently in each language, and small held-out sets make things look ready when they
   aren't. Measure from your own address, in every language you serve, and gate on a lower bound.
   [09](studies/09-search-engine-mix/), [10](studies/10-search-ranking-for-agents/),
   [13](studies/13-photo-facts/)
9. **Some facts must come from whoever is responsible for them.** Don't infer safety or accessibility
   from photos; ask the operator. [13](studies/13-photo-facts/)

Where these disagree with published guidance, the studies name it and say why: the Model Context
Protocol's names-first tool search (06), test-first development with coding agents (02), and
12-Factor Agents' "mostly deterministic code, with LLM steps sprinkled in" (12).

## Studies

| # | Study | Position | Evidence |
|---|---|---|---|
| 01 | [Decision models as a set-reading tool](studies/01-decision-model-set-filter/) | Give the agent a set filter: one yes-no question per item, answered by a decision model | Reproducible, 2,900 items; production agent |
| 02 | [Proof on the real seam](studies/02-proof-on-the-real-seam/) | Ban agent-written tests; prove each change on the real system | Production data, two codebases |
| 03 | [Where a decision model belongs](studies/03-where-a-decision-model-belongs/) | In the agent's tool list, not in its path: nine placements, one kept | Production data; reproducible routing cases |
| 04 | [What the checker sees](studies/04-what-the-checker-sees/) | Give a checker everything the agent read, and its false flags disappear | Reproducible |
| 05 | [One agent loop](studies/05-one-agent-loop/) | One agent per person, not sub-agents or background pipelines | Production data |
| 06 | [What a tool search returns](studies/06-tool-search-results/) | Every hit with its schema, and a plain "no tool here does it" | Reproducible; production data |
| 07 | [Reasoning off for one decision](studies/07-reasoning-off-per-decision/) | Retry the decision with a bigger budget; never turn reasoning off for the turn | Production data; reproducible experiment |
| 08 | [One false line](studies/08-one-false-line/) | Remove stale capability claims from history; instructions don't override them | Reproducible; production data |
| 09 | [Search engine mix](studies/09-search-engine-mix/) | Measure engines from your own address; don't pass a date filter to general search | Reproducible on any SearXNG; production data |
| 10 | [Search ranking for agents](studies/10-search-ranking-for-agents/) | Rank with a decision model and pass its top score on as "nothing matches" | Reproducible in 11 languages; production data |
| 11 | [Checking extracted facts](studies/11-checking-extracted-facts/) | A number check, then a judge that reads the whole source | Reproducible; production data |
| 12 | [Workflows versus one agent](studies/12-workflows-vs-agent/) | Fixed workflows fail off script; keep code only for exactness and the send boundary | Production data; reproducible experiment |
| 13 | [Photo facts](studies/13-photo-facts/) | Small heads on the image vectors you have, gated on a lower bound; no safety facts from photos | Reproducible with human labels; production data |

Related, in its own repository: [Tool calls, stop tokens and missing issue text: Gemma 4 as a coding agent](https://github.com/shawnbaako/gemma4-agent-failure-analysis).

## Hardware notes

- [Tesla P40 at a 125 W limit](hardware/p40-thermals/): clock, power and temperature over ten weeks.
  At the power limit, heat costs about 13% of clock speed by 80 °C, and an idle downclock keeps the card
  at 31 °C instead of 60 °C.

## How to read a study

Every study opens the same way: **our position** in a few sentences, **the evidence** for it in a few
bullets, and its **status** (what is reproducible, what it cost). Then come what happened in production,
the experiment and its results, what to build, the pitfalls we hit, and related work, including who
disagrees. Each also tries the simple alternative a builder would reach for first: keyword search,
BM25, a rule, a default.

Reproducible experiments use synthetic or public data only. Production figures are aggregates.

## Where the work comes from

The production data comes from two systems. One is an assistant that works for the people of a small
firm, in chat and in the background (studies 01, 03–09 and 12). The other is a travel commerce service
that outside AI assistants search and book through (studies 10, 11 and 13). Study 02 covers both.

The positions and the decisions are ours. Coding agents built the harnesses, ran the experiments and
drafted the write-ups under our direction. Unless a study says otherwise, labels and "hand checks" were
done by an LLM agent, not a person, and each study says which. Study 13 measures agent labels against
human ones from public data sets, because that is the check most of the other studies could not make.

## Terms

- **Decision model.** A small hosted model that answers one typed question (yes or no, one of several
  options, a score) with a probability, for a fraction of a cent. The ones tested here are Jev 1.13 and
  1.14 (TypeSafe), Clef and Clef Flash (Cloudflare) and Laya, an open checkpoint. They are called over
  the System One protocol, where `noul` is the yes-no question type.
- **Production models.** The agent's chat and background models: DeepSeek V4.1 Flash (the default),
  V4.1 Flash 1017 (the stronger option) and V4 Flash 0731 (the fast one).
- **Progressive disclosure.** A few tools listed on every turn; the rest found with a `find_tools`
  search and run by name with `run_tool`.
- **Restored copy.** A fresh copy of the production database in a private server, so a change can be
  replayed against real data, roles and row security, with the production models.
- **Outcome eval.** An eval that judges what happened (what changed, what reached a person), never
  wording or the order of tool calls.
- **Held out, lower bound.** Thresholds are fitted on a development split and results reported on a
  held-out split. A lower bound is the 95% Wilson lower bound on a proportion.

## Licence

Code is under the Apache License 2.0 (see `LICENSE`). Text, figures and data are under CC BY 4.0.
