# 02 · Deleting the test suite: proofs on real seams instead of tests

**Question.** A product built almost entirely by coding agents had 895 test files (320,000 lines, 0.78
lines of test per line of source) and still shipped defects the tests did not see. On 2026-10-20 the
suite was deleted and new tests were banned. A change is now proved on the real seam it touches.
What changed afterwards, what did it cost, and what does the evidence say against it?

**Status.** Draft case report from one private repository. The numbers below come from that
repository's git history and its written evidence; they cannot be recomputed from this folder. It is
one team, one product and 26 days of "after". Read it as a report of what happened, not as a result
that generalises.

**Short version.**

- The time spent on tests was large and it stopped: 71% of commits touched a test file, and 40% of changed code lines were test lines.
- The suite had been green through serious defects, including one that passed 11,631 tests and five reviews.
- The suite was not useless. A mutation audit a month earlier found it caught 12 of 15 injected defects.
- One production outage after the deletion was squarely covered by a deleted test, and it landed five hours after the deletion.
- The share of pull requests that are fixes did not fall (42% before, 45% after).
- Throughput fell by about 70% in the same weeks, for reasons that mostly have nothing to do with testing. Nothing here isolates the effect of the testing change.

## The practice

A change is proved by its effect on the real seam it changes:

| What changed | What counts as proof |
|---|---|
| What the agent does | A replay on a restored copy of production, under real roles and row security, with the production models. The outcome is judged against the design intent; different sound approaches are accepted. |
| An integration with an outside service | The real service, within what was authorised. Record what was called and clean up. |
| A deterministic guarantee (access, ledgers, money arithmetic, migrations) | Source checks against the restored copy, plus one pass as each affected role. |
| A page | The page in a browser, used as a person would use it. |

Three rules sit under this:

- **A rehearsal is not a proof.** A step that replaces part of the seam (a scripted model, a patched function, a test client in place of the route, a stub schema, a synthetic row) is reported as rehearsed, with what was replaced named. It never counts as a pass.
- **Evals judge outcomes.** A case judges which effect happened, what was asked and how often a person was interrupted. It never asserts wording, tool order or the current implementation.
- **Evidence is written down.** Each piece of work records what ran, against what, the result, the cleanup and what remains unproved.

Continuous integration still runs the lint, the type check, the web build, every migration on an empty
database and a source check that fails if a test file or test runner appears. It takes about a minute.

## Why

The suite had become the measure of done. Coding agents wrote tests alongside every change, the tests
asserted what the code did, and a green run was reported as verification. Three things followed:

- **Tests pinned the implementation.** Removing a structure meant rewriting the tests that described it, so the suite defended the machinery it was supposed to check.
- **Green did not mean working.** The defects that reached people were in behaviour under production conditions: real row security, real model output, real mail. Tests on scratch data with scripted models did not exercise those.
- **The cost was most of the work.** See the first two rows of the table below.

## Before and after

"Before" is the four weeks from 2026-09-22 to 2026-10-19. "After" is 2026-10-20 to 2026-11-14 (26 days;
the last week is partial).

| Measure | Before | After |
|---|---|---|
| Test files / test lines / ratio to source lines | 895 / 320,463 / 0.78 | 0 |
| Commits touching a test file | 1,241 of 1,738 (71%) | 3 of 441 |
| Changed code lines that were test lines | 40% | 0.1% |
| Commits about fixing tests or CI, per week | 11, 13, 16, 14 | 0 |
| CI duration | 48–55 minutes | about 66 seconds |
| Commits per week | 494, 424, 391, 429 | 217, 88, 123, 13 |
| Merged pull requests per week | 95, 49, 30, 53 | 23, 23, 25, 5 |
| Median pull request | 20 files, 1,600 lines | 13.5 files, 727 lines |
| Pull requests from a `fix/` or `repair/` branch | 96 of 227 (42%) | 34 of 76 (45%) |
| Written evidence folders added | 60 | 75 |

The suite grew from 125 test files in late August to 895 in eight weeks. The deleting commit removed
336,665 lines.

What the written evidence contains, by keyword match over each folder:

| Mentions | After (75 folders) | All earlier folders (77) |
|---|---|---|
| A restored production copy | 61 | 25 |
| Production models | 45 | 3 |
| A browser pass | 46 | 37 |
| A real outside service | 23 | 10 |
| A step labelled "rehearsed" | 31 | 11 |
| A section on what remains unproved | 66 | 20 |
| Test-pass counts cited as evidence | 4 | 28 |

Model spend on proofs is recorded in 19 of the 75 folders and sums to about $32. The rest is not recorded.

## Green suite, wrong behaviour (before)

- A change passed 11,631 tests and five reviews. In production its stall check saw no rows under row security and stopped every run at ten minutes.
- Tool-call markup leaked into 95 of 716 streamed replies over ten days while the suite was green.
- An eval was accepted at 102 of 102 with 24 gates passing. It never judged the output it was about.
- Twenty assertions passed on any exception; an injected connection-pool timeout passed a permission test.
- A review of one morning's production behaviour found 37 defects, including four of nine emails marked "verified" that were wrong.
- Panel sign-in had 205 tests. None checked the ticket's signature.

## Regressions after, and whether a deleted test covered them

| Regression | Covered by a deleted test? |
|---|---|
| Contact saves failed for about 22 hours (a write passed an explicit null) | **Yes.** A database-backed test ran exactly this write. The breaking commit landed five hours after the deletion. |
| Tool-search results lost their input schemas; a week later the agent looped on tools it could find but not call | **Partly.** A deleted test asserted the schema was present, so the removal would have gone red. The looping itself needs a real model; the tests used a scripted one. |
| A retry after a cut-off reply asked for the whole output budget and one write reasoned through 131,072 tokens | **Partly.** Adjacent retry-bound tests existed; whether they would have failed is not established. |
| A real model made 106 placeholder file creations in one run | **No.** |
| A person's standing permission ended when its task closed | **No.** |
| A field stopped being written on drafts, silently disabling a downstream feature | **No.** |

The change that removed the schemas had itself been measured on a restored-copy replay, and still
shipped the defect. A proof shows the case that was run; it is not a guard on the cases that were not.

Proofs did catch defects before merge: a replay that surfaced six defects in one consolidation, a first
proof run that showed a runaway turn, a container build that would have failed on a deleted path, and a
calculation that came back as 0.3547 and was reported as 35.47%.

## Evidence against

- **The suite caught most injected defects.** A mutation audit a month before the deletion introduced 15 defects one at a time; the suite caught 12. It also found that 70% of test files touched a real database and that mock-only assertions were almost absent. The claim that the tests were theatre did not hold as stated. What held was narrower: the three survivors were serious (one was sign-in accepting any signature), and the suite's coverage was of code paths, not of production conditions.
- **A deleted test would have stopped a production outage.** See the first row above.
- **The fix share did not fall.** 42% of pull requests before and 45% after came from a fix branch.
- **Proofs leave no regression guard.** A proof is run once and written up. Nothing reruns it when a neighbouring change lands. Several of the regressions above were found by a person in production.
- **Proofs are partial.** 66 of 75 evidence folders list unproved items and 31 contain rehearsed steps. An audit of stand-ins after the change found fakes in every category.
- **Restored production copies are real data.** They need the same access controls as production, and many teams could not use them at all.

## What else changed at the same time

None of the before-and-after differences can be attributed to the testing change alone.

- The agent's architecture was consolidated the next day, with a large cut in tools and background paths.
- Several product surfaces were retired in the same week; source shrank from 408,000 to 328,000 lines.
- The mix of coding agents changed: one agent's share of commits fell from 600 to 47.
- Hosted CI stopped running on the same day for an unrelated billing reason, so the CI-time comparison is partly forced.
- Review-gated work orders and a cheaper eval method started within three weeks.

## Reading

Stated as carefully as the evidence allows:

1. Agent-written tests consumed most of the work and described the implementation. Removing them removed that cost and stopped test counts being offered as proof. The written evidence afterwards is about production conditions far more often.
2. The suite was catching real defects when it was deleted, and one outage followed directly. Deleting everything discarded the database-backed tests of deterministic behaviour along with the rest.
3. Proof on the real seam finds the defects tests could not see here. It does not guard against regression, and it has not reduced the share of work that is fixes.

The open question this report cannot answer is whether a small set of deterministic, database-backed
checks, kept beside the proofs, would have prevented the contact-save outage without bringing back the
cost. The practice already keeps such checks for access, ledgers and money; the outage was just outside
that line.

## Related work

Most critics of unit testing argue for fewer or better tests, not none. That is the main thing a
reader should hold against this report.

**Against unit tests and mocks**

- Coplien, "Why Most Unit Testing is Waste", 2014. https://pythontest.com/strategy/why-most-unit-testing-is-waste/
- Hansson, "TDD is dead. Long live testing.", 2014. https://dhh.dk/2014/tdd-is-dead-long-live-testing.html. And Beck, Fowler, Hansson, "Is TDD Dead?", 2014. https://martinfowler.com/articles/is-tdd-dead/
- Dodds, "Write tests. Not too many. Mostly integration.", 2019. https://kentcdodds.com/blog/write-tests
- Trenk and Bly, "Test Doubles", and Graves, "Larger Testing", in *Software Engineering at Google*. https://abseil.io/resources/swe-book/html/ch13.html, https://abseil.io/resources/swe-book/html/ch14.html. Real implementations first; larger tests are slow, flaky and hard to own.
- Shore, "Testing Without Mocks: A Pattern Language", 2023. https://www.jamesshore.com/v2/projects/nullables/testing-without-mocks. Rejects mocks and also rejects broad end-to-end tests as the main suite.

**Testing against production or production-shaped state**

- Majors, "I test in prod", 2019. https://increment.com/testing/i-test-in-production/. "You should test before and in prod."
- GoReplay. https://github.com/buger/goreplay. Diffy. https://github.com/opendiffy/diffy. Replay of real traffic and response comparison.
- FoundationDB, "Simulation and Testing". https://apple.github.io/foundationdb/testing.html. The opposite route to fidelity: deterministic simulation.

**Tests written by language models**

- Konstantinou, Degiovanni, Papadakis, arXiv 2410.21136. https://arxiv.org/abs/2410.21136. Generated oracles mainly capture actual behaviour, bugs included.
- Mathews and Nagappan, "Design choices made by LLM-based test generators prevent them from finding bugs", arXiv 2412.14137. https://arxiv.org/abs/2412.14137
- Hora and Robbes, "Are Coding Agents Generating Over-Mocked Tests?", MSR 2026. https://arxiv.org/abs/2602.00409
- Banik, Chowdhury, Shamim, "All Smoke, No Alarm", IEEE AITest 2026. https://arxiv.org/abs/2606.18168. 80.2% of 86,156 agent test patches have a weak or missing oracle.
- Against: Jhanglani et al., "Beyond Test Presence", arXiv 2607.12068. https://arxiv.org/abs/2607.12068. Agent tests have near-human assertion strength.

**Evals that grade outcomes**

- Grace, Hadfield, Olivares, De Jonghe (Anthropic), "Demystifying evals for AI agents", 2026. https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Yao, Shinn, Razavi, Narasimhan, "τ-bench", 2024. https://arxiv.org/abs/2406.12045
- Shankar et al., "Who Validates the Validators?", 2024. https://arxiv.org/abs/2404.12272. Judges drift; outcome evals inherit that.

**Evidence for tests**

- Nagappan, Maximilien, Bhat, Williams, "Realizing quality improvement through test driven development", *Empirical Software Engineering* 13(3), 2008. Defect density fell 40–90% for 15–35% more development time.
- Yuan et al., "Simple Testing Can Prevent Most Critical Failures", OSDI 2014. https://www.usenix.org/conference/osdi14/technical-sessions/presentation/yuan
- Petrović, Ivanković, Fraser, Just, "Does mutation testing improve testing practices?", ICSE 2021. https://arxiv.org/abs/2103.07189
- Freire (Nubank), "Why We Killed Our End-to-End Test Suite", 2021. https://building.nu.com/why-we-killed-our-end-to-end-test-suite/. The nearest account of a removal, and they added contract tests in its place.

**Similar practice with coding agents**

- McCarthy (StrongDM), "Software Factory", 2026. https://factory.strongdm.ai/. Held-out scenarios in place of in-repo tests, scored against simulated third-party services. Those simulations are what this report calls a rehearsal.
- Willison, "Your job is to deliver code you have proven to work", 2025. https://simonwillison.net/2025/Dec/18/code-proven-to-work/. Evidence from a real run, and automated tests are also "not optional".
- Wang et al., "The Verification Horizon", arXiv 2606.26300. https://arxiv.org/abs/2606.26300. Every verifier is a proxy for intent.
