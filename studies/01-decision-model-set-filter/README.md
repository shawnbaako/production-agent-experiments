# 01 · Decision models as a set-reading tool

**Our position.** When an agent has to answer a question about a whole set (1,500 mail threads, 600
open promises, 800 accounts), give it a set-filter tool: the agent writes one yes-no question, a small
decision model answers it for every item in parallel, and the agent reads the top of the ranked list.
Keyword search misses what people write without the keyword, and embeddings blur the distinction the
agent actually asked about. A decision model ranks the right items to the top for a few cents per
thousand items.

**Result.** On a synthetic corpus with hard near-misses, every hosted decision model put 25 or 26 of
the 26 planted items in its top 10. Embeddings found 18, BM25 16 and keyword search 9. A production
agent given the tool found 30 of 30 planted items on mailbox-wide questions, against 22 to 23 without
it.

Everything is reproducible from this folder: the corpus, the harness and every per-item answer from Jev
1.13 and 1.14, Clef, Clef Flash, Laya and the baselines. Next: a local LLM read through its answer
probabilities, and harder items.

## What is here

| File | What it is |
|---|---|
| `corpus.py` | Generator for the synthetic corpus (seeded, deterministic) and the frozen question wordings |
| `bench.py` | Runs a scorer over the corpus, caches every answer, and computes the report |
| `results/answers/*.jsonl` | One row per (scorer, question, item): the score, latency and token count |
| `results/report.json` | Metrics recomputed from the answers by `python3 bench.py report` |

Standard library only. `python3 bench.py --help` lists the scorers and how to point one at an endpoint.

## Corpus

Everything is invented: a fictional consulting firm, 26 fictional clients, `.example` addresses.

| Set | Items | Questions | Held-out positives |
|---|---|---|---|
| Mail threads | 1,499 (1,440 templated background, 59 hand-written) | renewal price, competitor mentioned, client at risk | 6, 5, 3 |
| Promises | 600, each read against one of three new client emails | does this email change this promise? | 2 per email |
| Accounts | 800 (776 templated, 24 hand-written) | runs its own clinical laboratory? | 6 |

- **Planted positives** are written the way people write, often without the obvious keyword.
- **Near-misses** share the keywords or the topic: a web-domain renewal, a vendor's subscription price,
  the client's own competitors, a lab-equipment distributor, a clinic that sends all tests out.
- **Negations** state the opposite ("we are not talking to any other consultants").
- **Split.** Every item was assigned to `dev` or `held` by the seed before any model was asked.
  Thresholds are fitted on `dev` and reported on `held`. The question wordings and one rewording of each
  were frozen before the first held-out run.
- **Labels** are the generator's intent, written by an LLM agent. No person has relabelled them.

Positives are rare by design (2 to 6 per question in the held-out half), as they are in a real mailbox.
Each per-question number therefore rests on a handful of items. Read the pooled figures first.

## Method

Each scorer gives every item a score for the question. The report then asks how many planted positives
are in the top 10 and top 25 of the ranking, with ties broken against the scorer.

- **Decision model** (`systemone`): one yes-no (`noul`) question per item over the Jev-style
  `/v1/systemone` protocol. The score is the returned probability of yes.
- **Local LLM** (`logprob`): one chat request per item, one output token, scored as P(yes) / (P(yes) + P(no))
  from the token log-probabilities.
- **Embeddings**: cosine similarity between the question (for promises, the new email) and the item.
- **BM25**: the question (for promises, the new email) against the item.
- **Keyword**: substring match on the terms a person would type (`renew`, `competitor`, `lab`, the client's name).

## Results

Held-out half. Each cell is positives found in the top 10 out of positives, with AUROC in brackets.

| Scorer | renewal price | competitor | at risk | promise e1 | promise e2 | promise e3 | clinical lab | Pooled, top 10 | Pooled, top 25 |
|---|---|---|---|---|---|---|---|---|---|
| Clef (`cloudflare/clef`) | 6/6 (1.000) | 5/5 (1.000) | 3/3 (1.000) | 2/2 (1.000) | 2/2 (0.998) | 2/2 (1.000) | 6/6 (1.000) | **26/26** | 26/26 |
| Jev 1.14 (`typesafe/jev-1.14`) | 6/6 (1.000) | 5/5 (1.000) | 3/3 (1.000) | 2/2 (0.996) | 1/2 (0.968) | 2/2 (0.999) | 6/6 (1.000) | **25/26** | 26/26 |
| Jev 1.13 (`typesafe/jev-1.13`) | 6/6 (1.000) | 5/5 (1.000) | 3/3 (1.000) | 2/2 (0.997) | 1/2 (0.973) | 2/2 (1.000) | 6/6 (1.000) | **25/26** | 26/26 |
| Clef Flash (`cloudflare/clef-flash`) | 6/6 (1.000) | 5/5 (1.000) | 3/3 (1.000) | 2/2 (0.987) | 2/2 (0.997) | 2/2 (0.998) | 5/6 (0.970) | **25/26** | 25/26 |
| Laya `typed-decisions` (local CPU) | 6/6 (1.000) | 3/5 (0.986) | 0/3 (0.970) | 1/2 (0.799) | 2/2 (0.990) | 0/2 (0.481) | 6/6 (0.999) | **18/26** | 21/26 |
| EmbeddingGemma 2 (local) | 6/6 (1.000) | 2/5 (0.976) | 2/3 (0.692) | 1/2 (0.967) | 1/2 (0.954) | 1/2 (0.970) | 5/6 (0.990) | **18/26** | 22/26 |
| BM25 | 3/6 (0.689) | 4/5 (0.968) | 1/3 (0.743) | 1/2 (0.982) | 2/2 (1.000) | 1/2 (0.972) | 4/6 (0.830) | **16/26** | 18/26 |
| Keyword substring | 1/6 | 1/5 | 1/3 | 2/2 | 2/2 | 2/2 | 0/6 | **9/26** | 9/26 |

Hosted models were called through OpenRouter on 2026-11-15, one `noul` question per item, 10,700 calls each
(held-out, dev and the reworded held-out pass):

| Scorer | Latency p50 / p95 | Mean input tokens | Cost for 10,700 calls | Answers flipped by rewording, at the fitted thresholds |
|---|---|---|---|---|
| Clef | 328 / 826 ms | 239 | $0.49 | 9 |
| Jev 1.14 | 188 / 268 ms | 373 | $0.17 | 26 |
| Jev 1.13 | 186 / 254 ms | 373 | $0.17 | 22 |
| Clef Flash | 273 / 522 ms | 239 | $0.05 | 37 |
| Laya, local CPU (4 threads) | 408 / 565 ms | 130 | no fee | 54 |

What these runs show:

- **Every decision model beats the retrieval baselines on this corpus**, and keyword search finds about a third of what they find.
- **The corpus does not separate the decision models on ranking.** All four are within one item of each other. It is too easy for that purpose; harder items are the next addition.
- **They differ in how stable a cut-off is.** Thresholds fitted on `dev` ranged from 0.19 to 0.99 across questions and models. Rewording one question (competitor mentioned) moved 20 answers across the threshold for Jev 1.14 and 23 for Clef Flash, and 1 for Clef, while AUROC stayed at 0.998 or above for all three. The ranking survives rewording; a fixed cut-off does not.
- **The keyword row is not a ranking.** A substring match gives 0 or 1, and ties are broken against the scorer, so a common term such as "lab" places no positive in the top 10.

- **Laya, the open checkpoint, does as well as the hosted models on direct factual questions** (renewal
  price, clinical lab) and falls behind on judgement and on comparing two texts. It found none of the
  three at-risk clients in its top 10, and on one of the promise questions its ranking was no better
  than chance (AUROC 0.48). Overall it sits level with the embedding model (18 against 18 in the top 10).
- **Laya's scores are the least stable under rewording**: 54 answers crossed the fitted threshold, and
  its fitted thresholds sat between 0.24 and 0.60, much closer together than the hosted models'.
  Laya's own model card warns that it ships over-confident and needs a temperature refit.

A local LLM read through its answer probabilities has not been run.
<!-- results:end -->

### First run (2026-10-18)

The benchmark was first run with Jev 1.13 on 2026-10-18: 25 of 26 in the top 10 and 26 of 26 in the
top 25. Its per-item answers were not kept. The Jev 1.13 row above is a fresh run and gives the same
two figures.

Misses in both runs follow the same pattern: a promise on the same topic for a different client scores
high, and an indirect effect scores low ("interview the plant manager", after an email saying the
plant manager had left).

### Observation from a production agent (not reproducible here)

The same operator was offered as a tool to a private tool-calling agent (DeepSeek V4.1 Flash) over this
corpus loaded into a scratch mailbox. One trial per arm and request:

| Arm | Agent used the tool | Planted items found, three mailbox-wide requests |
|---|---|---|
| Tool in the agent's visible tool list | 3 of 3 | 30 of 30 |
| Tool reachable only through a tool-search tool | 0 of 12 requests | 22 of 30 |
| Tool absent | — | 23 of 30 |

When the set was small enough to filter by client, the agent did not use the tool in any arm, which is
the behaviour wanted. With the tool, each request cost one to three cents more in total: the agent's own
spend fell 15% to 46%, and the decision model added about $0.03 per 1,500 threads.

This is one system, one model and one trial per cell. It is reported because the comparison of a listed
tool against a searchable one has been asked for elsewhere (see related work) and we found no published
measurement.

## Building the tool

- **Return the ranking with probabilities and counts, never a silent cut.** Fitted thresholds ran from
  0.19 to 0.99 across questions and models, and rewording one question moved up to 23 answers across
  its threshold while the ranking held.
- **Let the agent write the question.** In production the agent's own wording was often better than
  ours, and it chose not to use the tool when a filter by client was enough.
- **List the tool.** Reachable only through tool search, it was never used.
- **Mind the item length.** Items here are short (about 70 tokens); a real thread costs more per item
  and leaves more for the model to read past. Clip each item to what the question needs.
- **Pick the model by stability, not only ranking.** On this corpus the hosted models rank alike; Clef
  held its answers under rewording best (9 flips against 26 for Jev 1.14 and 37 for Clef Flash). Laya
  matches them on plain factual questions and falls behind on judgement.

## Related work

The operator is not new. What this study adds is one corpus on which the hosted, open and local
scorers can be compared with the cheap baselines, and the listed-against-searchable observation above.

**Semantic filters and pointwise yes-no scoring**

- Patel et al., "Semantic Operators and Their Optimization: Enabling LLM-Based Data Processing with Accuracy Guarantees in LOTUS", PVLDB 18(11), 2025. https://arxiv.org/abs/2407.11418. `sem_filter` asks a predicate per row and uses a cheap-model cascade; it returns a cut, not a ranking.
- Nogueira, Jiang, Lin, "Document Ranking with a Pretrained Sequence-to-Sequence Model" (monoT5), 2020. https://arxiv.org/abs/2003.06713. The probability of a relevance word as a pointwise score.
- Turnbull, "Bag of Decisions Reranker", 2026-10-08. https://softwaredoug.com/blog/2026/10/08/bag-of-decisions.html. Summed Jev yes-probabilities as a reranker.
- Coates (Elastic), "Using Jev as a search reranker: benchmarks and how to implement", 2026-09-30. https://www.elastic.co/search-labs/blog/ecommerce-search-reranking-llm-alternative-jev

**Decision models compared**

- Rafe and Das, "Benchmarking System One decision models against trained classifiers and language models for automated decision gates", arXiv 2610.00346. https://arxiv.org/abs/2610.00346. A local LLM read through answer probabilities matches Jev on two of four datasets; Laya trails zero-shot.
- Deußer et al., "Evaluating and Benchmarking the System One Model Jev", arXiv 2609.37647. https://arxiv.org/abs/2609.37647
- van Deth, "Jev vs 25 Lines of Python: Typed Decisions Tested on 450 Dutch Texts", 2026. https://vincentvandeth.nl/blog/jev-vs-diy-logprobs-typed-decisions-benchmark
- akitaonrails, jev-docs-benchmarks. https://github.com/akitaonrails/jev-docs-benchmarks. Jev, Clef, OpenAI Decisions and Laya with raw responses.
- Laya model card. https://huggingface.co/convaiinnovations/laya

**Tools an agent can see against tools it must search for**

- Anthropic, "Introducing advanced tool use", 2025-11-24. https://www.anthropic.com/engineering/advanced-tool-use. Advises keeping the three to five most-used tools loaded and deferring the rest.
- anthropics/claude-code issue #84312, 2026-08-05. https://github.com/anthropics/claude-code/issues/84312. Reports deferred tools being reached for less reliably and proposes the loaded-against-deferred comparison.
- Gan and Sun, "RAG-MCP", 2025. https://arxiv.org/abs/2505.03275. Fei, Zheng, Feng, "MCP-Zero", 2025. https://arxiv.org/abs/2506.01056

**Where a decision model sits in an agent system**

- Pernelle, "Jev in Production: What Worked, What We Rolled Back", 2026-09-22. https://audiala.com/blog/jev-in-production/. A decision-model router in front of the agent was rolled back; a per-candidate scorer was kept.
- Runkle and Lovell (LangChain), "Building a Harness with Jev", 2026-09-17. https://www.langchain.com/blog/building-a-harness-with-jev. The decision model as middleware before the model call.
