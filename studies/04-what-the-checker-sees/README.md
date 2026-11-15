# 04 · What the checker sees: checking an agent's output against the right evidence

**Question.** A small decision model checks each sentence an agent writes: is it supported by the
sources? In a production agent this checker was given only the sources the output cited, and most of
its flags turned out to be true sentences the agent had taken from other records it read. The checker
was removed (see [study 03](../03-where-a-decision-model-belongs/)). Does giving the checker everything
the agent read fix the false flags, and are the real errors still caught when it has more to read?

**Status.** Reproducible: synthetic data, every answer committed, about $0.23 for all hosted runs.

**Short version.**

- **Given only the cited sources, the checker flags almost every sentence that came from another
  record.** Jev 1.14 flagged 94% of them and Clef Flash 97%, about 3.7 false flags per output. Clef
  flagged 56%. The checker was right that those sentences are not in the cited sources; that is
  exactly why its flags were noise to a reviewer.
- **Given everything the agent read, those false flags disappear and the errors are still caught.**
  With the full evidence set every hosted model flagged at most 1 of 89 such sentences, and caught 46
  to 49 of the 53 planted errors in the held-out half, against 47 to 51 with the cited sources only.
- **Separating errors from true sentences went from moderate to near perfect:** AUROC 0.62–0.78 to
  0.98–0.99 for errors against sentences grounded in other records.
- **The cost is a longer state.** Input per question rose from 350–480 tokens to 650–780, and cost per
  output from $0.0002 to $0.0004 for Jev 1.14.
- **The remaining noise is non-claims.** Greetings, sign-offs and offers are still flagged by some
  models (24 of 42 for Jev 1.14, 40 of 42 for Clef Flash, 3 of 42 for Clef). A checker should skip
  sentences that make no claim, or ask that first.

## Data

Everything is invented: the same fictional consulting firm as study 01, invented clients and people,
`.example` addresses.

- **48 outputs** an agent might write: 16 email replies, 12 client updates, 10 short research briefs,
  10 meeting follow-ups. 535 sentences in all.
- **Each output has two kinds of record:**
  - *cited*: what the output replies to or cites (an email thread, a fetched page, a KPI sheet);
  - *other*: what else the agent read through its tools (CRM records, internal notes, earlier threads,
    calendar lookups, a page that returned an error). Some are distractors that no sentence uses.
- **Every sentence is labelled:**

  | Label | Sentences | Meaning |
  |---|---|---|
  | `cited` | 166 | Supported by a cited record |
  | `other` | 174 | Supported only by one of the other records; a true statement a reviewer would accept |
  | `not_a_claim` | 86 | Greetings, sign-offs, questions, offers with no factual content |
  | `unsupported` | 47 | Planted error: supported by no record |
  | `contradicted` | 62 | Planted error: a record contradicts it (cited or other) |

- **Planted error types** (109): wrong number 20, wrong date 18, a claim the source does not make 17,
  an invented promise 17, a reversed fact 13, an invented price 12, the wrong person 12. They are
  subtle: a week off, 182 staff for 192, "as Dana said" when it was Priya.
- **Split:** outputs with an even number are development (fitting thresholds), odd numbers are held
  out (everything reported). Each half has 24 outputs.
- **Labels** are the author's intent, written by an LLM agent (Claude) and re-read case by case; no
  person has relabelled them. The author flagged sentences in six cases as hard to label and left
  them as written: c08 (a confirmation that is only in a note), c16 and c21 (a correct ratio from a
  wrong total; a "nearly half" that is 35%), c30 (an unsupported earlier figure), c33 (online check-in
  read as online booking) and c34 (relabelled after a record was expanded).
- **Length:** every case's records stay under 1,300 words, because Clef reads only about the first
  2,000 tokens of its input on Workers AI.

## Method

One yes-no (`noul`) question per sentence: *"Is this sentence stated in, or supported by, the records
above?"* The state is the records followed by the sentence. A sentence is flagged when P(yes) is below
a threshold fitted on the development half (best F1 for finding errors among sentences that make a
claim). Three conditions:

| Condition | Records in the state |
|---|---|
| `cited` | Only the cited records |
| `all` | The cited records and every other record the agent read |
| `all_reworded` | As `all`, with the question reworded: *"Do the records above back up what this sentence says?"* The threshold is reused from `all` |

## Results

Held out: 24 outputs, 271 sentences, 53 planted errors, 89 sentences grounded in other records, 87 in
cited records, 42 non-claims.

| Model | Evidence | Errors caught | Of `other` flagged | Of `cited` flagged | True sentences flagged per output | AUROC, errors vs true |
|---|---|---|---|---|---|---|
| Jev 1.14 | cited only | 49/53 | 94% | 5% | 3.67 | 0.828 |
| Jev 1.14 | everything read | 49/53 | 1% | 1% | 0.08 | 0.987 |
| Jev 1.14 | everything, reworded | 48/53 | 1% | 1% | 0.08 | 0.987 |
| Clef | cited only | 47/53 | 56% | 0% | 2.08 | 0.884 |
| Clef | everything read | 49/53 | 1% | 1% | 0.08 | 0.989 |
| Clef | everything, reworded | 49/53 | 1% | 0% | 0.04 | 0.991 |
| Clef Flash | cited only | 51/53 | 97% | 9% | 3.92 | 0.800 |
| Clef Flash | everything read | 46/53 | 0% | 2% | 0.08 | 0.977 |
| Clef Flash | everything, reworded | 45/53 | 0% | 1% | 0.04 | 0.986 |

| Laya (local CPU) | cited only | 45/53 | 82% | 15% | 3.58 | 0.713 |
| Laya (local CPU) | everything read | 22/53 | 20% | 10% | 1.12 | 0.763 |
| Laya (local CPU) | everything, reworded | 31/53 | 28% | 23% | 1.88 | 0.762 |

Laya, the open `typed-decisions` checkpoint, cannot do this job. Its input window holds a few hundred
tokens of state (423 on average here, against 650–780 for the hosted models), so the full evidence set
is cut before the model reads it, and error recall falls to 22 of 53. Even with only the cited records
it flags 15% of correct cited sentences.

"True sentences" are `cited` and `other`. Non-claims are reported separately below.

**Cost and size**, through OpenRouter on 2026-11-15, 1,605 calls per model:

| Model | Mean input tokens, cited / everything | Cost per output, cited / everything | Latency p50 |
|---|---|---|---|
| Jev 1.14 | 483 / 776 | $0.00023 / $0.00036 | 206 ms |
| Clef | 353 / 647 | $0.00075 / $0.00138 | 319 ms |
| Clef Flash | 353 / 647 | $0.00007 / $0.00014 | 304 ms |

**Non-claims flagged** (of 42, held out, everything read): Jev 1.14 24, Clef 3, Clef Flash 40.

**Errors missed** with everything read, by type: the misses are concentrated in the wrong person (Jev
1.14 and Clef caught 4 of 6, Clef Flash 3 of 6) and wrong numbers (6 or 7 of 8). Every model caught all
10 claims a source does not make and all 9 wrong dates, and 7 or 8 of the 8 invented promises.

## What this shows

- **A checker's false flags are mostly an evidence mismatch, not a model weakness.** The same models
  that flagged nearly every `other` sentence with the cited records flagged almost none with
  everything the agent read, at the same accuracy on errors. Most flags in the production checker
  came from exactly this mismatch.
- **More evidence did not drown the errors.** Doubling the state did not lower error recall for Jev
  1.14 or Clef. Clef Flash lost five errors, so the smallest model is the one where a longer state
  costs something.
- **The stable part is the ranking, again.** The reworded question changed error recall by at most one,
  with the threshold carried over from the original wording.

## Building a checker that works

- **Give it what the writer read.** Send the tool results the agent used, not only the documents the
  output cites. Most false flags in our production checker came from this mismatch.
- **Skip sentences that make no claim.** Greetings and offers are where the remaining flags are. Ask
  "does this sentence state a fact?" first, or filter them out before checking.
- **Fit the threshold on your own outputs.** Fitted thresholds here ran from 0.09 to 0.50 depending on
  model and evidence set; the default of 0.5 is wrong for most of them.
- **Mind the input window.** Clef reads about the first 2,000 tokens of text on Workers AI, and Laya
  far less. A long evidence set needs a model that reads it all, or a cut you choose deliberately.
- **Use the flags in the run.** A flag is most useful returned to the agent before it finishes, so it
  can fix or cite the sentence, not shown to a reviewer who reads the draft anyway.

## Files

- `cases.py`: the 48 cases, records and sentence labels.
- `check.py`: runs a scorer over every sentence in each condition, caches the answers and computes the
  report. Standard library only.
- `results/*.jsonl`: every answer; `results/report.json`: the metrics recomputed from them.

## Related work

- Tang, Laban, Durrett, "MiniCheck", EMNLP 2024. https://arxiv.org/abs/2404.10774. Small fact-checkers
  matching a large model on grounding documents, for a fraction of the cost.
- Laban, Schnabel, Bennett, Hearst, "SummaC", TACL 2022. https://arxiv.org/abs/2111.09525. Sentence-level
  consistency checking against a source document.
- Zha, Yang, Li, Hu, "AlignScore", ACL 2023. https://arxiv.org/abs/2305.16739
- Min et al., "FActScore", EMNLP 2023. https://arxiv.org/abs/2305.14251. Atomic facts checked against a
  knowledge source.
- Gao, Yen, Yu, Chen, "Enabling Large Language Models to Generate Text with Citations" (ALCE), EMNLP
  2023. https://arxiv.org/abs/2305.14627. Citation support measured against the cited passages.
- Yin et al., "ContextCheck", Findings of ACL 2026. https://aclanthology.org/2026.findings-acl.658/.
  Verifiers that read one sentence at a time miss context from the rest of the output.
- Onweller et al., "Cited but Not Verified", arXiv 2605.06635. https://arxiv.org/abs/2605.06635.
  Citation checking in research agents degrades as tool calls grow.
- Frank (Vals AI), "An Independent Evaluation of TypeSafe's Jev", 2026-10-06.
  https://vals.ai/blogs/independent-evaluation-of-jev

None of these measures the effect studied here: the same checker, on the same sentences, given the
cited sources or everything the writer read. Citation-support benchmarks such as ALCE check against
the cited passages by design, which is the setting in which this study's false flags appear.
