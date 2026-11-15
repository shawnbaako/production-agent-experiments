# 02 · Proofs, not tests: verifying software that coding agents write

**Our position.** Unit tests and hosted CI were built for human teams, where running the real system
was slow and expensive and a cheap proxy was the best you could afford. Coding agents change that
trade. An agent can restore a copy of production, replay a real request against its branch, drive a
browser, call the real service and read the result in minutes, so the proxy is no longer the cheap
option, and it was never the accurate one. Worse, when the same agent writes the code and the tests,
the tests describe what the code does, a green suite becomes the agent's stop condition, and the
suite defends the implementation against every later change.

So we deleted the test suite, banned new tests, and moved CI off hosted runners onto the machine that
can see production. Every change is proved on the real seam it touches: a replay on a restored copy of
production with the production models, the real outside service, a browser used the way a person uses
it, and outcome evals. Rehearsals with stand-ins are allowed as a fast inner loop and are never counted
as proof.

## Why the old practices stop fitting

| Practice | Why it made sense for people | What it does with coding agents |
|---|---|---|
| Unit tests beside every change | Running the whole system was slow, so check the parts | The agent can run the whole system on a production copy in minutes; the parts passing says little about the whole |
| Tests written with the code | A second look by the author, then a reviewer | The same agent writes both. The tests encode its own reading, bugs included, and agree with it by construction |
| Green suite as "done" | A shared, visible signal for a team | An agent optimises for the signal it is given. It stops when the suite is green, and edits or mocks until it is |
| A large suite as a safety net | Changes are expensive, so pin behaviour | Agents restructure and delete constantly. The suite pins the machinery you are trying to remove, and every removal starts with rewriting tests |
| Hosted CI on every push | A clean, neutral machine nobody can tamper with | It cannot see a production copy, the production models or the real accounts, so it can only run proxies. Its 48–55 minute loop is longer than most agent tasks |
| Mocks for outside services | Real calls were slow, costly or risky to set up | The mock is written by the same agent that writes the integration, so it agrees with the agent's assumptions about the service, which is where integration bugs live |

What agents make cheap is exactly what the old practices worked around: setting up realistic state,
exercising the real path end to end, and reading the result. Spend the effort there.

## What the suite looked like

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

### The verification ladder

| Rung | What it is | Counts as proof? | Typical time |
|---|---|---|---|
| Rehearsal | The change run with part of the seam replaced: a scripted model, a stub, a synthetic row, a test client | No. Reported as "rehearsed", with what was replaced named | Seconds |
| Local gate | Lint, type checks, the web build, every migration on an empty database in a throwaway server, and a check that no test file or runner has appeared | For source and schema only | About a minute |
| Replay on a restored copy | The branch's code against a fresh copy of production, under real roles and row security, with the production models | Yes, for what the agent and the service do | Minutes |
| Real service and browser | The real integration within what was authorised, with calls recorded and cleaned up; the page used as a person would | Yes, for integrations and pages | Minutes |
| Outcome eval | Cases judged on what happened, what was asked and what reached a person, never on wording or tool order; run once against the stored result of the previous step | Yes, and it is the regression guard | Minutes to an hour |

| What changed | Proof |
|---|---|
| What the agent does | A replay on a restored copy, judged against the intended behaviour; any sound approach passes |
| An integration | The real service, within what was authorised |
| A deterministic guarantee (access, ledgers, money, migrations, data writes) | Source checks against the restored copy, plus one pass as each affected role |
| A page | The page in a browser, at the sizes and themes people use |

Every change records what ran, against what, the result, the cleanup and what is still unproved.

### CI on the machine that can see production

Hosted CI's one real advantage is a machine the code under test cannot tamper with. We keep it for
exactly that case: code from outside, and work orders from coding agents that run without a person,
still run on hosted runners and never on the production host. Everything else runs locally:

- **The gate runs on the exact commit being pushed** and records the result as a commit status naming
  the checked tree. Hosted CI skips a tree that carries that record, so nothing is run twice and
  nothing is skipped on trust.
- **It refuses to record a dirty tree,** so the record always describes exactly what was pushed.
- **It starts and removes its own database server,** so a run never touches a shared database.
- **The proof kit runs on the same machine:** it restores a copy of production into a private server,
  runs a branch against it with the production models only when asked, serves the app for a browser,
  and drops the copy afterwards. None of that is possible on a hosted runner without moving production
  data and credentials onto it.

We had already decided to stop running the same checks twice before hosted CI minutes ran out; the
local gate was merged the day they did.

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
  database-backed test had covered exactly that write. Data writes belong with access, ledgers and money
  on the list of deterministic guarantees checked against the restored copy.
- **A proof covers what you ran, not what you didn't.** A change that removed input schemas from
  tool-search results was proved on a replay and still shipped a defect, because the replay never
  filled the tool list. When a change removes something, prove the case where its absence matters.
- **Stand-ins creep back.** Agents under pressure reach for fakes and call the result a proof. Name the
  rung ("rehearsed, not proved") in every report, and check for it in review.
- **A one-off proof is not a regression guard.** Behaviour that must not regress belongs in an outcome
  eval that is rerun, or in a deterministic check.
- **Local CI needs provenance.** A status that says "passed" without the tree it checked is a claim, not
  a record. Tie the record to the tree and refuse uncommitted changes.
- **Keep untrusted code off the machine with production access.** Only code your own sessions wrote runs
  locally. Anything from outside runs on hosted runners.

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
