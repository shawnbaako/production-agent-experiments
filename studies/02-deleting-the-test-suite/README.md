# 02 · Deleting the test suite: proofs on real seams instead of tests

**Our position.** When coding agents write most of the code, they also write most of the tests, and
those tests describe what the code does rather than what it should do. A green suite becomes the
measure of done while the defects that matter happen under production conditions the tests never
reach. We deleted the suite, banned new tests, and now prove every change on the real seam it touches:
a replay on a restored copy of production, the real outside service, a browser used the way a person
uses it, and evals that judge outcomes.

## Why we stopped testing

The suite grew from 125 test files to 895 in eight weeks, almost all of it written by coding agents
alongside their own changes. By the end:

| | |
|---|---|
| Test lines | 320,463, 0.78 for every line of source |
| Commits that touched a test file | 71% |
| Changed lines that were test lines | 40% |
| Commits spent fixing tests or CI | 11–16 a week |
| CI run | 48–55 minutes |

And it was green through the defects that reached people:

- A change passed 11,631 tests and five reviews. In production its stall check saw no rows under
  row-level security and stopped every run at ten minutes.
- Tool-call markup leaked into 95 of 716 streamed replies over ten days while the suite was green.
- An eval was accepted at 102 of 102, with 24 gates passing, without ever judging the output it was
  about.
- Twenty assertions passed on any exception; an injected connection-pool timeout passed a permission
  test.
- One morning's review of production behaviour found 37 defects, including four of nine emails marked
  "verified" that were wrong.
- Sign-in had 205 tests. None checked the token's signature.

The suite was not empty theatre. A mutation audit injected 15 defects and it caught 12. That is the
point: it was good at catching the defects it was written for, which are the ones a coding agent
already avoids, and blind to the ones that come from real data, real permissions, real model output
and real mail. It also pinned the implementation. Removing a structure meant rewriting the tests that
described it, so the suite defended the machinery it was meant to check.

## What we do instead

A change is proved by its effect on the seam it changes:

| What changed | Proof |
|---|---|
| What the agent does | A replay on a restored copy of production, under real roles and row security, with the production models. The outcome is judged against the intended behaviour; any sound approach passes. |
| An integration | The real service, within what was authorised. Record what was called; clean up. |
| A deterministic guarantee (access, ledgers, money, migrations) | Source checks run against the restored copy, plus one pass as each affected role. |
| A page | The page in a browser, used as a person would use it. |

Three rules hold it together:

1. **A rehearsal is not a proof.** Anything that replaces part of the seam (a scripted model, a patched
   function, a test client instead of the route, a stub, a synthetic row) is reported as rehearsed,
   with what was replaced named. It never counts as a pass.
2. **Evals judge outcomes.** A case checks which effect happened, what was asked and how often a person
   was interrupted. It never asserts wording, tool order or the current implementation.
3. **Evidence is written down.** Every change records what ran, against what, the result, the cleanup
   and what is still unproved.

CI still runs lint, type checks, the web build, every migration on an empty database, and a check that
fails if a test file or test runner appears. It takes about a minute.

## What changed

| | Before | After |
|---|---|---|
| Test files | 895 | 0 |
| Commits touching a test file | 71% | under 1% |
| Changed lines that were test lines | 40% | 0.1% |
| Commits spent fixing tests or CI | 11–16 a week | 0 |
| CI run | 48–55 minutes | about 1 minute |
| Median pull request | 20 files, 1,600 lines | 13.5 files, 727 lines |

What the written evidence for each change contains:

| Evidence mentions | Before (77 records) | After (75 records) |
|---|---|---|
| A restored production copy | 25 | 61 |
| The production models | 3 | 45 |
| A real outside service | 10 | 23 |
| A browser pass | 37 | 46 |
| A section on what is still unproved | 20 | 66 |
| Test-pass counts offered as evidence | 28 | 4 |

The work moved from keeping a suite green to showing behaviour under production conditions. Proofs
caught defects before merge that no test here had seen: a replay that surfaced six defects in one
consolidation, a first run that showed a runaway turn, a container build that would have failed, and a
calculation that returned 0.3547 and reported it as 35.47%.

## Pitfalls

- **Deterministic writes still need a check on a real database.** After the deletion, a change wrote an
  explicit null into a non-null column and contact saves failed for about a day. A deleted
  database-backed test had covered exactly that write. Our rule already keeps checks for access,
  ledgers and money; data writes belong on the same list, run against the restored copy.
- **A proof covers what you ran, not what you didn't.** A change that removed input schemas from
  tool-search results was proved on a replay and still shipped a defect, because the replay never
  filled the tool list. When a change removes something, prove the case where its absence matters.
- **Stand-ins creep back.** Workers under pressure reach for fakes and call the result a proof. An audit
  after the change found stand-ins in every category. Name the rule ("rehearsed, not proved") and check
  for it in review.
- **A proof is not a regression guard.** It is run once and written up. Behaviour that must never
  regress belongs in an outcome eval that is rerun, or in a deterministic check.

## Related work

**Against unit tests and mocks**

- Coplien, "Why Most Unit Testing is Waste", 2014. https://pythontest.com/strategy/why-most-unit-testing-is-waste/
- Hansson, "TDD is dead. Long live testing.", 2014. https://dhh.dk/2014/tdd-is-dead-long-live-testing.html.
  Beck, Fowler and Hansson, "Is TDD Dead?", 2014. https://martinfowler.com/articles/is-tdd-dead/
- Dodds, "Write tests. Not too many. Mostly integration.", 2019. https://kentcdodds.com/blog/write-tests
- Trenk and Bly, "Test Doubles", and Graves, "Larger Testing", in *Software Engineering at Google*.
  https://abseil.io/resources/swe-book/html/ch13.html, https://abseil.io/resources/swe-book/html/ch14.html.
  Real implementations first; the costs of larger tests.
- Shore, "Testing Without Mocks: A Pattern Language", 2023. https://www.jamesshore.com/v2/projects/nullables/testing-without-mocks

Most of these argue for fewer and better tests, not none. We go further because the author of the code
and the author of the tests are now the same agent.

**Tests written by language models**

- Konstantinou, Degiovanni, Papadakis, arXiv 2410.21136. https://arxiv.org/abs/2410.21136. Generated
  oracles mainly capture actual behaviour, bugs included.
- Mathews and Nagappan, "Design choices made by LLM-based test generators prevent them from finding
  bugs", 2024. https://arxiv.org/abs/2412.14137
- Hora and Robbes, "Are Coding Agents Generating Over-Mocked Tests?", MSR 2026. https://arxiv.org/abs/2602.00409
- Banik, Chowdhury, Shamim, "All Smoke, No Alarm", IEEE AITest 2026. https://arxiv.org/abs/2606.18168.
  80.2% of 86,156 agent test patches have a weak or missing oracle.
- Jhanglani et al., "Beyond Test Presence", 2026. https://arxiv.org/abs/2607.12068. A counterpoint:
  agent tests with near-human assertion strength.

**Testing against production state, and outcome evals**

- Majors, "I test in prod", 2019. https://increment.com/testing/i-test-in-production/
- GoReplay, https://github.com/buger/goreplay, and Diffy, https://github.com/opendiffy/diffy, for replay of
  real traffic and response comparison.
- Grace, Hadfield, Olivares, De Jonghe (Anthropic), "Demystifying evals for AI agents", 2026.
  https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents. Grade the final state, not the path.
- Yao, Shinn, Razavi, Narasimhan, "τ-bench", 2024. https://arxiv.org/abs/2406.12045
- Shankar et al., "Who Validates the Validators?", 2024. https://arxiv.org/abs/2404.12272

**The case for tests**

- Nagappan, Maximilien, Bhat, Williams, "Realizing quality improvement through test driven development",
  *Empirical Software Engineering* 13(3), 2008.
- Yuan et al., "Simple Testing Can Prevent Most Critical Failures", OSDI 2014.
  https://www.usenix.org/conference/osdi14/technical-sessions/presentation/yuan. Its lesson is our first
  pitfall: error paths in deterministic code deserve a check.
- Petrović, Ivanković, Fraser, Just, "Does mutation testing improve testing practices?", ICSE 2021.
  https://arxiv.org/abs/2103.07189

**Close to our practice**

- McCarthy (StrongDM), "Software Factory", 2026. https://factory.strongdm.ai/. Held-out scenarios in
  place of in-repo tests. They score against simulated services; we would call that a rehearsal.
- Willison, "Your job is to deliver code you have proven to work", 2025.
  https://simonwillison.net/2025/Dec/18/code-proven-to-work/
- Freire (Nubank), "Why We Killed Our End-to-End Test Suite", 2021. https://building.nu.com/why-we-killed-our-end-to-end-test-suite/
- Wang et al., "The Verification Horizon", 2026. https://arxiv.org/abs/2606.26300. Every verifier is a
  proxy for intent.
