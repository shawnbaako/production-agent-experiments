# 03 · Where a decision model belongs in an agent: nine placements, one kept

**Question.** A decision model answers a typed question (yes or no, one of several options, a score)
with a probability, for a fraction of a cent. Where does one belong in an agent system: in front of
the agent, behind it, inside its tools, or in its hands?

**Status.** Case report from one private production agent. The measurements were made on that
system's own records, so only aggregate numbers are given here and none can be recomputed from this
folder. The one experiment that used synthetic data is reproducible in
[study 01](../01-decision-model-set-filter/).

**Short version.**

- A decision model was tried in nine places over five weeks. Eight were measured in one batch of seven experiments, and four of those were adopted into production the next day.
- Within eight days three of the four had been removed, although two of them had measured well.
- The one that stayed is a tool the agent decides to call. Every removed use was a fixed step the agent could not choose: a step before it ran, a check on what it wrote, a reading added to its tools' results, or a review after it finished.
- What decided each removal was not accuracy. It was where the model sat and who acted on its answer.

## Setting

- **The agent:** a tool-calling loop that works for a small firm, in chat and in background runs. Production model at the time: DeepSeek V4.1 Flash.
- **The decision model:** TypeSafe Jev 1.13 through OpenRouter. The surviving use now runs on Jev 1.14.
- **The experiments:** 2026-10-18, each with a frozen question wording, a development split for fitting thresholds and a held-out split for the reported numbers. Total spend about $6.30, of which Jev itself was under $1.
- **Labels:** reference labels were careful readings by LLM agents (Claude), not by a person. A spot audit of 24 labels in one experiment found no disagreement.

## Timeline

| Date | What happened |
|---|---|
| 2026-09-25 | Decision model added as a step before the agent: it picked "the record this request is about" and ranked a daily list |
| 2026-10-05 | That step removed, after sixteen patch commits in nine days |
| 2026-10-18 | Seven experiments run |
| 2026-10-19 | Four adopted: run review, output checker, "already done?" reading, set filter. Model routing removed |
| 2026-10-20 | Output checker and "already done?" deleted |
| 2026-10-27 | Run review removed |
| Today | The set filter remains, as a tool the agent calls |

## The uses and what happened to each

| Use | Where it sat | What was measured (held-out) | Outcome |
|---|---|---|---|
| Pick the subject before the agent runs | Fixed step in front of the agent | Accuracy never recorded | Removed after nine days |
| Route a delegated task to a model profile | Fixed step in front of a sub-task | 85 synthetic cases: 91.8% as deployed, 100% reworded; a keyword rule 97.6% | Removed. In production it chose the default 9 times out of 9 |
| Review each finished run | Fixed step after the agent | 120 runs: repeated work precision 0.92, recall 0.95; ended-without-a-result 0.86, 0.86 | Adopted, then removed after eight days |
| Check each sentence of the agent's output against its sources | Fixed step on the agent's writes | 36 outputs, 941 sentences: precision 0.87, recall 0.81; 46 of 49 planted errors caught | Adopted, then deleted the next day |
| "Has this already been done?" | Fixed reading inside three tools | 86 issued items: 51 of 65 real repeats found, against 15 for an exact-id rule | Adopted, then deleted the next day |
| Readings on each arriving event | Fixed annotation on evidence | "Asks for something": AUROC 0.73, precision 0.08. No reading predicted whether the agent acted (AUROC 0.42–0.64) | Never adopted |
| Learn what a person acts on | Trained layer beside the agent | 209 labels: AUROC 0.97 from the item's type alone, 0.95 with text, 0.67 for the zero-shot decision model | Dropped |
| Choose between two generated images | Fixed step on the agent's output | 53 pairs: the model answered "first" 106 times out of 106 | Dropped; the images never reached the model |
| Set filter: one yes-no question per item over a large set | **Tool the agent chooses to call** | 25 of 26 planted items in the top 10, against 14 for keyword search | **Kept** |

## Why the ones that measured well were removed

**The output checker** flagged about a quarter of all sentences once it ran on real drafts. The
experiment had already shown why. In real research dossiers 59% of sentences were unsupported by the
sources the checker was given, and most of those (46% of all sentences) were grounded in things the
agent had read through other tools: account history, earlier correspondence, a page that returned an
error. They were correctly "not in these sources" and wrong as flags. A checker that sees only the
cited pages is checking a different evidence set from the one the writer used. Meanwhile a person
already read every draft before it was sent, so the checker added noise beside a boundary that did not
move.

**The "already done?" reading** found three times as many repeats as the exact-id rule, and it
over-flagged. It was one of four repeat guards stacked on the same symptom. The repeats came from several
background runs each deciding without the others' pending work in view. The fix chosen was to
remove that cause (one agent, with everything pending in view) and not to add a better guard.

**The run review** ran for a week in production: 27 runs reviewed, 4 flagged. The flags went to an
operations page and to no one else. The choice written down at the time was to deliver a flag into the
next run of the same work as a recorded fact, or to delete the review. It was deleted.

**Model routing** was accurate and pointless. In production only two of the profiles were eligible
for a tool-using sub-task, so the only decision it could make was between the default and one costlier
alternative, and it chose the default every time. With every profile offered, a reworded question
reached 98.8% and a keyword rule on the required output reached 94.1%.

## What stayed, and what was different about it

The set filter is in the agent's tool list. The agent writes the question, names the set, reads the
ranked result and decides what it means. It used the tool for mailbox-wide questions and did not use
it when filtering by client was enough. Nothing downstream consumes the probabilities without the
agent in between.

| Placement | Who acts on the answer | Fate here |
|---|---|---|
| Before the agent | The system, before the agent sees the request | Removed twice |
| On the agent's output | A person, as extra flags beside a review they already do | Removed |
| Inside tool results | The agent, whether or not it asked | Removed |
| After the run | Nobody | Removed |
| A tool the agent calls | The agent, when it judges the question needs it | Kept |

There is one condition on "kept": the tool had to be visible. When it was reachable only through a
tool-search tool, the agent never used it (0 of 12 requests). Listed, it used it for all three
mailbox-wide requests. Details are in study 01.

## Two cautions from the dropped experiments

**A 200 response does not mean the input arrived.** The image experiment sent images in the vendor's
native format (a top-level `assets` map and an opt-in header) through a gateway that forwards `state`
and `questions` only. Every request returned 200 with a usage receipt. Requests with invalid image
data, an unreferenced image or no opt-in header also returned 200. Input tokens with two images were
the same as for text alone, which is the cheapest check: compare the token count with and without the
image. The gateway's own image format works; the failure was the silent acceptance of the other one.

**A good ranking is not a usable threshold.** Rewording the "already done?" question flipped 27 of 86
answers. In study 01, thresholds fitted per question ranged from 0.19 to 0.99, and rewording one
question moved 20 answers across the threshold while AUROC stayed at 0.998. Anything built on a fixed
cut-off inherits that; a ranking shown to the agent does not.

## What this does not show

- **Other systems.** One agent, one firm, one decision model.
- **Human labels.** The reference labels were written by LLM agents.
- **The rare failure types.** The run review's questions about refusals, needless questions and unsupported claims had 4, 4 and 11 cases in 200 runs. They were never measured.
- **Whether a better-placed checker would have survived.** The output checker was removed before it was given everything the agent had read. That version was never built.
- **Production accuracy of the uses that were adopted.** They ran for one to eight days. The removals rest on what the flags were for, not on a production accuracy figure.

## Related work

**Placement of a decision model in an agent system**

- Pernelle, "Jev in Production: What Worked, What We Rolled Back", 2026-09-22. https://audiala.com/blog/jev-in-production/. The nearest published account: a router in front of the agent scored 27 of 28 offline and was rolled back in production; a per-candidate scorer inside retrieval was kept.
- Runkle and Lovell (LangChain), "Building a Harness with Jev", 2026-09-17. https://www.langchain.com/blog/building-a-harness-with-jev. The decision model as middleware before the model call or tool execution.
- Zhu et al., "JevAgentHarness", arXiv 2610.21412. https://arxiv.org/abs/2610.21412. Shared control between an agent and a decision model; delegating without a fitted threshold cost 19 points.
- Schluntz and Zhang (Anthropic), "Building effective agents", 2024. https://www.anthropic.com/engineering/building-effective-agents. Defines the routing workflow and advises the simplest solution possible.

**Routing**

- Ong et al., "RouteLLM", 2024. https://arxiv.org/abs/2406.18665. Chen, Zaharia, Zou, "FrugalGPT", 2023. https://arxiv.org/abs/2305.05176
- Li et al., "LLMRouterBench", arXiv 2601.07206. https://arxiv.org/abs/2601.07206. Several recent routers do not reliably beat a simple baseline.
- Li, "Rethinking Predictive Modeling for LLM Routing: When Simple kNN Beats Complex Learned Routers", 2025. https://arxiv.org/abs/2505.12601

**Checking output against sources**

- Tang, Laban, Durrett, "MiniCheck", EMNLP 2024. https://arxiv.org/abs/2404.10774. Small checkers at the accuracy of a large model for a fraction of the cost. The checker here replicates this with a different model.
- Yin et al., "ContextCheck", Findings of ACL 2026. https://aclanthology.org/2026.findings-acl.658/. Verifiers that read one sentence at a time miss cross-sentence context.
- Onweller et al., "Cited but Not Verified", arXiv 2605.06635. https://arxiv.org/abs/2605.06635. Citation checking in research agents degrades as tool calls grow.
- Frank (Vals AI), "An Independent Evaluation of TypeSafe's Jev", 2026-10-06. https://vals.ai/blogs/independent-evaluation-of-jev. Strong on claim checking against filings, weak on a legal-reasoning slice.

**Reviewing agent runs**

- Cemri et al., "Why Do Multi-Agent LLM Systems Fail?", 2025. https://arxiv.org/abs/2503.13657
- George et al., "Unsupervised Cycle Detection in Agentic Applications", 2025. https://arxiv.org/abs/2511.10650. Repetition detection over 1,575 trajectories.
- Shea and Roche (LangChain), "Can Jev Be a Better Agent Evaluator?", 2026-09-20. https://langchain.com/blog/jev-agent-evals-langsmith

**Wording and order sensitivity**

- Sclar et al., "Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design", ICLR 2024. https://arxiv.org/abs/2310.11324
- Zheng et al., "Large Language Models Are Not Robust Multiple Choice Selectors", ICLR 2024. https://arxiv.org/abs/2309.03882
- Rafe and Das, arXiv 2610.00346. https://arxiv.org/abs/2610.00346. Swapping the yes and no option names flipped about half of a decision model's answers.

**Learning what a person acts on**

- Aberdeen, Pacovsky, Slater, "The Learning Behind Gmail Priority Inbox", 2010. https://research.google/pubs/the-learning-behind-gmail-priority-inbox/. The result here (metadata and a linear model beat zero-shot) is a small replication.

**Inputs that silently do not arrive**

- keltokhy/jevkit-core pull request 24, 2026-10-17. https://github.com/keltokhy/jevkit-core/pull/24. Documents the same gateway accepting and billing a request while dropping the `assets` map.
- Chen et al., "Are We on the Right Way for Evaluating Large Vision-Language Models?", 2024. https://arxiv.org/abs/2403.20330. Models score well with no image at all; run the blind control.
