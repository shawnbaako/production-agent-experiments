# Routing a delegated task with a decision model

The reproducible part of [study 03](../): 114 synthetic assignments, each labelled with the kind of
specialist it needs, and three ways of choosing one. The question is whether a decision model earns
its place as the router.

**Result.** It routes well, and a keyword rule routes almost as well. In the production system these
cases came from, the only choice the router could actually make was between the default and one
alternative, and it picked the default every time.

## Held-out results (76 cases)

Two offered sets. `prod` is what production could offer a tool-using sub-task (general or draft);
`full` offers all four. An answer of "unsure" runs on general.

| Selector | `prod` accuracy | `full` accuracy |
|---|---|---|
| Fixed `general` | 78.9% | 43.4% |
| Keyword rule on the required output | 97.4% | 93.4% |
| Jev 1.14, production question (v1) | 90.8% | 90.8% |
| Jev 1.14, second question (v2) | 100% | 98.7% |
| Jev 1.13, v1 | 90.8% | 89.5% |
| Jev 1.13, v2 | 100% | 98.7% |
| Clef, v1 | 100% | 93.4% |
| Clef, v2 | 100% | 98.7% |

Neither the decision models nor the keyword rule under-routed a case (sent specialist work to
general). Every decision-model error was over-routing: a general task sent to a specialist.

Stability of the production question, as answers that changed on the 76 held-out cases:

| | Options in reverse order | Question reworded |
|---|---|---|
| Jev 1.14, `prod` / `full` | 4 / 5 | 3 / 1 |
| Jev 1.13, `prod` / `full` | 5 / 3 | 3 / 1 |
| Clef, `prod` / `full` | 0 / 1 | 0 / 1 |

Reversing the options cost Jev four to seven points of accuracy on the production question. The second
question changed by at most one answer under reordering.

3,078 calls in all, $0.09, through OpenRouter on 2026-11-15.

## What this shows

- **The question matters more than the model.** Moving from the production wording to the second question took both Jev versions from about 91% to 100% on the `prod` set. The second question was written on the development split and frozen before the held-out pass.
- **A keyword rule is within a few points of the best selector**, at no cost and with nothing to replay when it is wrong.
- **Routing accuracy was not what decided the outcome.** See study 03: the router was removed because the only choice available to it in production was one it never needed to make.

## Limits

- Synthetic cases written and labelled by an LLM agent, not a person.
- 76 held-out cases; one case is 1.3 points.
- The original experiment (2026-10-18, Jev 1.13) also scored 9 real production assignments, which are not included here. On its 85 held-out cases it measured 91.8% (v1) and 100% (v2) on `prod`, and 97.6% for the keyword rule.

## Files

- `cases.py`: the cases, the definitions and the frozen question wordings.
- `route.py`: runs a decision model over the cases and computes the report. Standard library only.
- `results/*.jsonl`: every answer; `results/report.json`: the metrics recomputed from them.
