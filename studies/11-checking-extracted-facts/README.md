# 11 · Checking extracted facts: a number check, then a judge that reads the whole source

**Our position.** Check the facts an agent extracts in two steps. First, a deterministic number and
unit check: the price, duration, capacity or age must be written in the fact's own excerpt. Then a
cheap decision model that reads the whole source. Never judge a fact from its cited excerpt alone. The
excerpt is a real quote, often with a true value, and the value can belong to a different offering. Only
the rest of the source shows that. This is [study 04](../04-what-the-checker-sees/)'s finding in a
second domain: what the checker is shown decides the result.

**The evidence**, from a production intake agent and a public replica on 130 Wikivoyage sections:

- **The same model, with only the evidence changed.** gpt-oss-safeguard-20b, an open model that
  classifies content against a written policy, given only each fact's excerpt wrongly downgraded 31.2%
  of 4,791 correct facts and let through 33 of 68 values copied from another offering. Given the whole
  source as well, it wrongly downgraded 20.6% and let through 7.
- **Cheap judges that read the whole source do the job.** Jev wrongly downgraded 1.7% of correct facts
  and caught every invented and copied value. A DeepSeek judge caught all 284 wrong facts and wrongly
  downgraded 2.7%.
- **The number check covers the decision model's blind spot.** Jev missed 3 of 92 swapped digits, all
  capacities; the number check caught all 92. Together, no wrong fact stayed marked as observed, for
  about $0.00013 a source.
- **Production agrees in direction.** The excerpt-only judge wrongly downgraded 25–27% and caught 37–50%
  of copied values; the whole-source judges 2.5–3.3% and 83–88%.
- **The whole source is necessary, not sufficient.** Even with it, the policy classifier rejected a fifth
  of correct facts. Part of that is a units mismatch (its fact lines show prices in cents against
  excerpts in dollars), which inflates its rates in production too.

**Status.** Reproducible, with production data. 130 public sources from English Wikivoyage, every model
answer committed, $0.71 through OpenRouter for everything. The production study's per-fact verdicts are
published in anonymised form.

## What happened in production

An intake agent reads an operator's own material (a pasted description, a spreadsheet, a PDF, a
photo of a price board, pages of their website) and proposes draft offerings: title, price,
duration, capacity, minimum age, what is included, cancellation terms and so on. Each fact carries a
status (`observed` when the material states it) and a short excerpt quoting where it was read. The
operator reviews the drafts before anything is sold. The only check before this study was a quote
check: an observed fact's excerpt must appear in the text that was read. It caught nothing, because
a wrong fact usually comes with a real quote.

The production study judged 993 observed facts from 35 sources (text, CSV and XLSX, PDF, photos,
websites), 90 of them wrong: 4 natural extractor errors (all photo misreads), 33 swapped digits or
units, 29 invented facts carrying an unrelated real line as their excerpt, and 24 values taken from
another offering in the same material. Every arm can only downgrade a fact from `observed` to
`inferred`. "False-supported" is the harm: a wrong fact still marked observed. "Wrongly downgraded"
is the cost: a correct fact the operator has to re-check.

| Arm (production) | False-supported | Wrongly downgraded | Caught: digit/unit swap (33) | Caught: invented (29) | Caught: other offering (24) | Caught: natural (4) |
|---|---|---|---|---|---|---|
| Quote check only | 100% | 1.6% | 0% | 0% | 0% | 0% |
| A1 number check | 44.4% (38–51) | 2.2% (0.6–4.4) | 100% | 58.6% | 0% | 0% |
| B Jev, whole source, @0.5 | 10.0% (3.5–17) | 3.3% (1.1–6.3) | 84.8% | 100% | 83.3% | 4 of 4 |
| C DeepSeek judge, whole source | 10.0% / 11.1% | 2.5% / 2.9% | 97.0% / 90.9% | 96.6% / 100% | 87.5% | 0 of 4 |
| D gpt-oss-safeguard, cited excerpt only | 16.7% / 20.0% | 25.0% / 26.9% | 100% | 100% | 50.0% / 37.5% | 1 of 4 |
| **A1 + B Jev @0.5** | **4.4%** (1.1–8.8) | **4.0%** (1.6–7.0) | 100% | 100% | 83.3% | 4 of 4 |

Two runs are shown as run 1 / run 2. Brackets are 95% bootstrap intervals over sources. Photos
reached Jev as OCR text; the full production table, with OCR and entailment arms, per-kind rates and
intervals for every cell, is in [`production/summary.md`](production/summary.md).

Two things in production motivated the replica. The excerpt-only judge (D) was a different model
from the whole-source judges (B and C), so "excerpt only" and "a weaker model" could not be told
apart. And the sample was small: 35 sources, 24 other-offering errors, most of the material written
by the agent that ran the study.

## The replica

**Data.** 130 sources, each one "See", "Do" or "Sleep" section of an English Wikivoyage article
about a US destination (86 articles, 38 states, 1,209 listings). A section lists several businesses
with their address, phone, hours, price and a description, which is close to an operator's own
material and makes "a value from another offering" possible. Every listing template is kept as
structured data (the ground truth) and rendered to the plain text a reader sees (what the extractor
reads). Median section length is 2,640 characters. Text is CC BY-SA 4.0; each source records its
page, section and revision ([`data/LICENSE-DATA.md`](data/LICENSE-DATA.md)). Only US destinations
were used, because the extraction prompt records prices in US cents.

**Extraction.** The production extractor, unchanged: DeepSeek V4.1 Flash 1017, the same prompt (its
rendered text hashes to the same SHA-256 as production's), the same output schema, temperature 0,
low reasoning effort, 16k output tokens and production's salvage of output cut at the budget. Each
section is given as a pasted text file, with no existing offerings. 125 of 130 sections produced
offerings (the other 5 were declined as a guide, not an operator's material), 1,114 in all; 5,612
facts were marked observed.

**Labels.** A natural fact is labelled correct when the listing it belongs to confirms it, by
field-specific rules in `labels.py`: the name, address, a dollar amount or "free" in the price, a
length stated in the description, at least 80% of description words in the listing, and production's
wording rules for prices, hours and terms. Facts the rules cannot confirm are left out of scoring
(134), as are facts from offerings that match no listing (388, mostly sub-offerings the extractor
split out of one listing) and business-contact facts (15), because a guide section has no single
operator. There is no public equivalent of production's natural errors, so that category is
production-only here.

**Injected errors.** Production's injection code, seed (20261101) and taxonomy, per source where
possible: one swapped digit or unit (92), one invented fact whose excerpt is an unrelated real line
(124), one value taken from another listing in the same section (68). One guard was added: a value
is not moved to a listing that states the same value, because the moved fact would then be true. The
scored set is 5,075 facts from 124 sources: 284 wrong and 4,791 correct.

**Arms.** All arms judge the same recorded facts, and all run on top of the quote check.

| Arm | What it reads | Request |
|---|---|---|
| A1 | The fact's excerpt | Production's number and unit check, deterministic |
| B | The whole section | Jev (`jev-latest`, served as `typesafe/jev-1.14-20261014`) on OpenRouter System One, one `noul` question per fact, batched per source; downgrade below 0.5 |
| C | The whole section | DeepSeek V4.1 Flash 1017 (the extractor) as a yes/no judge |
| D | Each fact's excerpt | `openai/gpt-oss-safeguard-20b` with production's written policy |
| Dw | The whole section and each excerpt | The same model and policy; "its source excerpt states" becomes "the source material states", and the section is prepended |

B, C and D use production's prompts, claim sentences, request bodies and parsers verbatim. Dw is
new: the only difference from D is what the judge reads. Every model arm ran twice.

## Results

5,075 scored facts (284 wrong, 4,791 correct) from 124 sources, run 1 of each arm. Brackets are 95%
bootstrap intervals over sources (2,000 resamples). Run 2 of each arm, thresholds 0.3 and 0.7, and
the per-section rates are in [`results/summary.md`](results/summary.md).

| Arm (replica, run 1) | False-supported | Wrongly downgraded | Caught: digit/unit swap (92) | Caught: invented (124) | Caught: other offering (68) |
|---|---|---|---|---|---|
| Quote check only | 99.6% | 0.6% | 0% | 0% | 1.5% |
| A1 number check | 50.4% (45.6–54.8) | 1.5% (1.0–2.0) | 100% | 36.3% | 5.9% |
| A1, reading "free" as 0 | 51.4% (46.7–55.9) | 0.6% (0.4–0.9) | 100% | 36.3% | 1.5% |
| B Jev, whole source, @0.5 | 1.1% (0.0–2.2) | 1.7% (1.3–2.2) | 96.7% | 100% | 100% |
| C DeepSeek judge, whole source | 0.0% (0.0–0.0) | 2.7% (2.0–3.6) | 100% | 100% | 100% |
| D gpt-oss-safeguard, cited excerpt only | 11.6% (8.5–14.9) | 31.2% (28.5–33.8) | 100% | 100% | 51.5% (39.0–63.1) |
| Dw gpt-oss-safeguard, whole source | 2.5% (0.7–4.3) | 20.6% (18.1–23.1) | 100% | 100% | 89.7% (82.1–96.7) |
| **A1 + B Jev @0.5** | **0.0%** (0.0–0.0) | **2.6%** (2.0–3.2) | 100% | 100% | 100% |
| A1 ("free" as 0) + B Jev @0.5 | 0.0% (0.0–0.0) | 1.7% (1.3–2.2) | 100% | 100% | 100% |
| A1 + C | 0.0% (0.0–0.0) | 3.6% (2.8–4.6) | 100% | 100% | 100% |

The quote check marks almost every wrong fact as observed, as in production. The number check
catches every swapped digit and unit and nothing else of note: an invented fact is caught only when
it is a number (an age, a capacity, a length) and the unrelated excerpt lacks it. Jev at 0.5 kept
three wrong facts, all capacities with two digits swapped ("Sleeps up to 16" claimed as 61, scored
0.85), the same blind spot production found; the number check catches all three. The DeepSeek judge
caught every wrong fact in both runs and downgraded somewhat more correct ones, most of them "what
the price includes".

### Same model: cited excerpt against whole source

The one change between D and Dw is the evidence: the same model, the same policy text apart from two
phrases, the same fact lines with their excerpts, and Dw also gets the section.

| gpt-oss-safeguard-20b, run 1 | False-supported | Wrongly downgraded | Caught: other offering | Wrongly downgraded, without price and duration facts |
|---|---|---|---|---|
| D, cited excerpt only | 11.6% (8.5–14.9) | 31.2% (28.5–33.8) | 35 of 68 (51.5%) | 26.9% |
| Dw, whole source | 2.5% (0.7–4.3) | 20.6% (18.1–23.1) | 61 of 68 (89.7%) | 16.3% |

- **Reading the whole source caught the copied values.** Wrong facts left as observed fell from 33
  to 7, and every one of the remaining misses in both arms is a value from another offering. An
  excerpt such as "Adults $13.25" is a true quote; only the rest of the section shows it is the
  aquarium's price, not the wax museum's.
- **It removed a third of the wrong rejections, not all of them.** 1,465 correct facts were
  downgraded with the excerpt only, 959 with the whole source. What remains is the model and its
  policy: "SUPPORTED only if the material states this exact value" rejects a category (`kind: stay`
  for a bed and breakfast) and most prices, which its fact lines give in cents (see below).
- **The model is not the right judge even with the whole source.** Jev and the DeepSeek judge,
  reading the same sections, wrongly downgraded 1.7% and 2.7%. Evidence decides whether a judge can
  catch a copied value; the model and its question decide how many correct facts it rejects on the
  way.

### Cost, latency and run-to-run agreement

| Run (replica) | USD per source | USD per 1,000 facts | Latency p50 / p95 per source | Run 1 vs run 2, same verdict |
|---|---|---|---|---|
| Extraction (for scale) | 0.00058 | n/a | 12.2 s | n/a |
| B Jev, batched | 0.00013 | 0.0029 | 0.2 / 0.4 s | 99.8% of 5,612 facts (at 0.5) |
| C DeepSeek judge | 0.00030 | 0.0066 | 8.1 / 18.9 s | 98.8% |
| D gpt-oss-safeguard, excerpt only | 0.00091 | 0.0202 | 2.9 / 5.3 s | 94.2% |
| Dw gpt-oss-safeguard, whole source | 0.00103 | 0.0230 | 3.3 / 5.8 s | 89.9% |

Jev's probabilities were identical or nearly so between runs: 12 facts of 5,612 crossed 0.5, none of
them changing a result in the table. In production its two batched runs agreed on all 993 facts.
gpt-oss-safeguard was the least stable and, given more to read, less stable still. All arms ran
through OpenRouter on 2026-11-15; Jev resolved to `typesafe/jev-1.14-20261014` on every call,
DeepSeek was served by Sail Research and gpt-oss-safeguard by Groq. Latencies for gpt-oss-safeguard
include retries after upstream rate limits.

Jev's probability tracks correctness (run 1, scored facts): below 0.1, 0 of 269 were correct;
0.1–0.3, 45%; 0.3–0.5, 97.7% of 44; above 0.9, 100% of 4,265. A threshold of 0.3 instead of 0.5
halves its wrong downgrades (0.8%) and lets through one more copied value (4 wrong facts kept, not
3).

## Production and replica

- **The excerpt-only judge fails the same way in both.** Wrongly downgraded: 25.0% and 26.9% in
  production, 31.2% here. Values copied from another offering caught: 50% and 37.5% in production,
  51.5% here. The same-model arm shows this is the evidence, not only the model.
- **Whole-source judges are cheap and accurate in both, and better here.** Production: 2.5–3.3%
  wrongly downgraded, 83–88% of copied values caught. Replica: 1.7–2.7% and 100%. Production's
  copied values came from a sibling product of the same operator, such as another tier of the same
  rental; here they come from another business, with a different name. The replica's 100% is an
  upper bound.
- **The number check does the same job in both.** Every swapped digit or unit caught, in both. Its
  share of invented facts differs (58.6% against 36.3%) only because more of the replica's invented
  fields are words (languages, cancellation terms) rather than numbers.
- **Jev's blind spot repeats.** Production: Jev missed 5 of 33 swaps, "all capacities or durations
  where the claim and the source differ only in the number". Replica: 3 of 92, all capacities. In
  both, the number check in front of Jev closes it: 4.4% false-supported in production, 0.0% here.
- **Not tested here.** Natural extractor errors (production's four were photo misreads) and the OCR
  path. These are production-only.

## What this adds to study 04

- **A second domain.** Study 04 checked sentences of written outputs against email threads, CRM
  records and notes. This study checks structured facts extracted from public travel listings, with
  a different extractor, a different question and a different set of models. The same thing decides
  the result: what the checker is shown.
- **The same model on both sides.** Study 04 compared evidence sets with the same models; production
  here did not, and its excerpt-only arm was also its weakest model. Dw removes that confound.
- **Errors a cited excerpt cannot show.** The value from another offering is the case study 04 could
  not have: the citation is real and the value is true, for a different thing. Only a checker that
  reads around the excerpt can see it.

## Building a fact checker for extraction

- **Run the number check first.** It is free, deterministic and caught every swapped digit or unit
  in both studies. It needs to read "free" as zero: the production version did not, and that one gap
  was 42 of its 72 wrong downgrades here.
- **Then ask a cheap judge with the whole source.** Batch every fact of a source into one request;
  in production, batching gave the same verdicts as one question per request at a fifteenth of the
  cost.
- **Do not ask about a fact using only its excerpt.** The excerpt is the extractor's own claim about
  where it read the fact. A judge confined to it rejects anything inferred or joined (kind, a
  description assembled from fragments) and cannot see that the quoted value belongs to someone
  else.
- **Write values the way the source does.** The excerpt judge was shown `price_minor: 9900` against
  "$99" and rejected most correct prices: 291 of 343 with the excerpt, 258 of 343 with the whole
  source, 48 of 57 in production. Jev's claim sentence turns cents into dollars, and it rejected 2
  of 343. Give a judge the value in the source's units, or convert it in the claim.
- **Choose the threshold on your own facts.** Jev's probability tracks correctness, but the useful
  cut differs: in the replica 98% of facts scored 0.3–0.5 were correct, so 0.5 costs reviews that
  0.3 would not.
- **Keep the last mile human.** "What the price includes" was where both whole-source judges and our
  own labels disagreed most; amenities a hotel offers are not always in the price. Show the operator
  the flagged facts rather than discarding them.

## Pitfalls

- **The extractor refused a travel guide.** Given the Wikivoyage URL as a website source, the
  extractor declined one of three pilot sections as "not one operator's own material". Giving each
  section as a pasted text file fixed it; 5 of 130 sections were still declined. A study that reuses
  a production prompt on public data has to present the data in a shape the prompt accepts.
- **The excerpt judge's prices were in cents.** See above; it inflates D's wrong downgrades in both
  studies. Without prices and durations, D still wrongly downgraded 26.9% of the remaining correct
  facts with the excerpt only and 16.3% with the whole source (production, excerpt only: 18.7%).
- **Labels by rule are lenient.** A rule that says the words of an "includes" item appear in the
  listing accepts a restaurant as included in a room price; the hand check found 3 such labels in 22
  disagreements reviewed. Production's fuzzy title match can also attach a fact to the wrong listing
  ("Provincetown Art Association and Museum" to "Provincetown Museum"), which then leaves a true
  fact unscored.
- **Groq rate-limits gpt-oss-safeguard-20b.** As in production, upstream HTTP 429s; failed sources
  were retried on the next run with backoff, and the latency figures include the retries' last try.

## How we measured

- **Hand check, ground truth.** 40 scored facts drawn at random (5 of each injected type, 25
  labelled correct) were read against their listings by the study's author, an LLM agent (Claude),
  not by a person. The author agreed with all 40 labels. The sample is mostly names, addresses,
  descriptions and prices, the fields that dominate the scored set.
- **Hand check, verdicts.** 29 facts where an arm disagreed with the label, read the same way: 10 of
  Jev's downgrades of correct-labelled facts, 5 of the DeepSeek judge's, 7 of the excerpt judge's,
  and 7 wrong facts an arm kept (3 by Jev, 4 by the excerpt judge). All 7 kept facts were really
  wrong. Of the 22 downgrades, the arm was wrong in 15, the label was wrong in 3 (a restaurant, a
  bar and a parking fee counted as part of a price) and 4 were judgement calls (hotel facilities as
  "included", which of two prices is standard, a name the extractor composed). All 7 excerpt-judge
  downgrades were wrong: a category, or an address with the city added. The label errors all favour
  the judges, so the wrongly-downgraded rates of B and C are, if anything, slightly high. Details in
  [`results/hand_check.json`](results/hand_check.json).
- **Bootstrap.** Sources are resampled with replacement, 2,000 times, seed 11, and each rate is
  recomputed; the interval is the 2.5th to 97.5th percentile. Facts from one source are not
  independent, so resampling facts would understate the width.
- **Spend.** Every call's OpenRouter-reported cost is appended to
  [`results/spend.jsonl`](results/spend.jsonl), and the code refuses a call once recorded spend
  reaches 95% of USD 5. The ledger includes an extraction pilot of three sections given as a website
  (USD 0.001), an arms pilot on two sources, and a first arms pass discarded after a labelling rule
  was fixed to read "free" as a price of zero (USD 0.048 for the last two). Calls in flight when a
  run was restarted are not in the ledger.
- **Production export.** Production's per-fact verdicts are in
  [`production/facts.jsonl`](production/facts.jsonl), keyed by salted, truncated SHA-256 ids, with
  the source kind, field, label, error type and every arm's verdict or probability. No source text,
  fact value, name or address is included. The same `report.py` recomputes production's table from
  it: the numbers match the production study's to the decimal. Costs are in
  [`production/costs.json`](production/costs.json).

## Files and how to rerun

- `fetch.py`: reads the Wikivoyage revisions and writes `data/sources.json`. Standard library only.
- `common.py`: the extractor's output models and prompt (`extract_prompt.txt`), the OpenRouter call
  and the spend ledger.
- `labels.py`: the label rules and production's error injection. `checks.py`: arm A1.
- `arms.py`: arms B, C, D and Dw. `report.py`: metrics and intervals for the replica and production.
- `run.py`: the stages. Every stage records its output and skips what is recorded, so a rerun makes
  no calls.
- `results/`: extractions, facts, every arm's answers, `report.json`, `summary.md`,
  `hand_check.json`, `spend.jsonl`. `production/`: the anonymised production verdicts and their
  report.

```
uv run python run.py report                                   # recompute everything, no network
OPENROUTER_API_KEY=... uv run python run.py extract           # only what is not recorded
uv run python run.py facts
OPENROUTER_API_KEY=... uv run python run.py arms B_1 Dw_1
```

## Related work

- [Study 04](../04-what-the-checker-sees/): the same effect for sentence checkers, with synthetic
  business records.
- Gero, Singh, Cheng, Naumann, Galley, Gao, Poon, "Self-Verification Improves Few-Shot Clinical
  Information Extraction", 2023. https://arxiv.org/abs/2306.00024. The extractor cites the span each
  value came from and checks itself. The span makes review easier; this study shows a span is not
  enough evidence for a second checker on its own.
- Li, Yue, Liao, Sun, "AttributionBench", 2024. https://arxiv.org/abs/2402.15089. Automatic
  attribution evaluators reach about 80% macro-F1, with many errors traced to fine-grained
  information and to a mismatch between what the model sees and what annotators used.
- Liu, Zhang, Liang, "Evaluating Verifiability in Generative Search Engines", Findings of EMNLP
  2023. https://arxiv.org/abs/2304.09848. Only 74.5% of citations supported the sentence they were
  attached to: a citation is a claim, not evidence.
- Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", NeurIPS 2023.
  https://arxiv.org/abs/2306.05685. Self-enhancement bias. In production the extractor judging its
  own photo reading (arm C) caught none of the four misreads.
- OpenAI, gpt-oss-safeguard-20b model card. https://huggingface.co/openai/gpt-oss-safeguard-20b. A
  21B open-weight model that classifies content against a policy written at inference time.
- Frank (Vals AI), "An Independent Evaluation of TypeSafe's Jev", 2026-10-06.
  https://vals.ai/blogs/independent-evaluation-of-jev
- Wikivoyage, "Listings". https://en.wikivoyage.org/wiki/Wikivoyage:Listings. The listing template
  fields used as ground truth.

None of these compares the same checker given a cited span and given the whole source, on extracted
structured facts.
