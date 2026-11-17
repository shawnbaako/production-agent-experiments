# 02 · Proof on the real seam, not agent-written tests

**Our position.** When coding agents write the code, delete their tests and ban new ones: all of them,
fake-adapter "integration" tests included. Make "done" mean the change works on the real seam it
touches, the place where the code meets real data, a real service or a person. Show it with evidence
the agent can't shape: a replay on a restored copy of production with the production models, the real
outside service, a browser used the way a person uses it, an outside assistant driving the product,
the persisted record read back, and outcome evals as the regression guard. Guard money, access and
data writes with structure and a check against a real database, not with test volume.

When the same agent writes the code and the tests, the tests describe what the code does, bugs
included. A green suite becomes the agent's stop condition, and the suite then defends the
implementation against every later change. Unit tests and hosted CI were a cheap proxy for human
teams, who could not afford to run the real system on every change. An agent can restore production,
replay a real request and drive a browser in minutes. The proxy is no longer the cheap option, and it
was never the accurate one.

**The evidence**, from the coding agents' own session logs and the git history of two production
codebases:

- Of 89 written-up defects in codebase 2, unit tests found none, before or after the deletion. Both
  suites were green through the defects that reached people.
- Before the deletion, a quarter of the agents' edits in codebase 1 touched a test file (19% in
  codebase 2). After a red test, the agent's next edit changed the test rather than the code 56% of
  the time.
- Deleting only the unit tests made agents write tests faster than ever, as fake-adapter integration
  tests. Redefining proof is what worked: commits touching tests fell to 9%, and browser, staging and
  outside-assistant actions rose from 12 to 139 per 1,000 tool calls.

**Status.** Design position, with production data. The codebase-2 scripts and aggregates are in
[`codebase-2/`](codebase-2/), ready to point at your own repository.

We did this in two production codebases, and both arrived at the same place:

| | Codebase 1 | Codebase 2 |
|---|---|---|
| What it is | An assistant product: a chat agent and background agents working for people | A commerce system: businesses publish what they sell, outside AI assistants search and book it, Stripe takes payment |
| Coding agents | pi (mostly OpenAI Codex models), Claude Code, Codex CLI | Claude Code, Codex, pi |
| How the suite grew | 125 to 895 test files in eight weeks | 225k to 1.01M test lines in six months |
| How tests were removed | Whole suite deleted and all new tests banned at once | Unit suites deleted first; ten days later all new tests banned and fakes named as mocks |

The difference in the last row is the most useful result here. In codebase 1, test work fell to 0.5%
of the agents' tool calls straight away. In codebase 2, removing only the unit tests made agents write
tests faster than at any point that year, as fake-adapter "integration" tests, until proof itself was
redefined. **Deleting tests doesn't change what agents do. Changing what counts as proof does.**

## Why the old practices stop fitting

| Practice | Why it made sense for people | What it does with coding agents |
|---|---|---|
| Unit tests beside every change | Running the whole system was slow, so check the parts | The agent can run the whole system on a production copy in minutes; the parts passing says little about the whole |
| Tests written with the code | A second look by the author, then a reviewer | The same agent writes both. The tests encode its own reading, bugs included, and agree with it by construction |
| Green suite as "done" | A shared, visible signal for a team | An agent optimises for the signal it is given. It stops when the suite is green, and edits or mocks until it is |
| A large suite as a safety net | Changes are expensive, so pin behaviour | Agents restructure and delete constantly. The suite pins the machinery you are trying to remove, and every removal starts with rewriting tests |
| Hosted CI on every push | A clean, neutral machine nobody can tamper with | It cannot see a production copy, the production models or the real accounts, so it can only run proxies. In codebase 1 its loop was 48–55 minutes; in codebase 2 it was red for eight months |
| Mocks for outside services | Real calls were slow, costly or risky to set up | The mock is written by the same agent that writes the integration, so it agrees with the agent's assumptions about the service, which is where integration bugs live |

What agents make cheap is exactly what the old practices worked around: setting up realistic state,
exercising the real path end to end, and reading the result. Spend the effort there.

## What the suites looked like

| | Codebase 1 | Codebase 2 |
|---|---|---|
| Test lines at the peak | 320,463, 0.78 for every line of source | 1,013,532, 0.76 for every line of source |
| Commits that touched a test file | 71% | Over half; 64% in the ten days after the unit suites went |
| Changed lines that were test lines | 40% | 30–40% in a typical week |
| Commits spent fixing tests or CI | 11–16 a week | — |
| Test files created and deleted | — | 7,597 created in a year; of those deleted, half lived under 50 days and one in five under a week |
| Assertions | In 772 commits the agent changed a test's assertions with the code it tested | 114,000 added and 39,000 removed in ten months: one deleted for every three written |

— means the figure was not measured in that codebase.

Both suites were green through the defects that reached people.

Codebase 1:

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

Codebase 2:

- An FX service invented exchange rates when its API key was missing. Its two unit test files passed
  because they mocked the rates.
- Planner fixtures passed while real model requests exhausted the schema-repair loop.
- Checkout refused proposals that had "passed seeded-ledger tests".
- Push events disappeared while "pull retry tests passed".
- An audit found three defects "reported closed and were not", and "several existing tests asserted
  the defect outright".

Codebase 2 keeps a write-up of every defect whose cause wasn't obvious. Of 89, none was found by a unit
test, before or after the deletion:

| Found by | Before the deletion | After |
|---|---|---|
| Driving the product (browser, staging, HTTP) | 23 | 16 |
| Live evals with the real model | 4 | 7 |
| Code review or audit | 7 | 11 |
| Staging or production incident | 3 | 5 |
| CI | 3 | 0 |
| Reported by a person | 1 | 0 |
| Unknown or tooling | 3 | 6 |
| **Unit test** | **0** | **0** |

The suites weren't empty theatre. In codebase 1 a mutation audit injected 15 defects and the suite
caught 12. In codebase 2 unit tests caught a quote that multiplied differently from checkout, so a
customer would have been quoted one price and charged another. That is the point: the suites were good
at the defects they were written for, which are the ones a coding agent already avoids, and blind to
the ones that come from real data, real permissions, real model output, real providers and real mail.

## What tests do to coding agents

Run time is the smallest cost. We measured the rest from the coding agents' own session logs and from
git history. Codebase 1 had 34,266 tool calls in the weeks before the deletion and 242 sessions after.
Codebase 2 had about 2,400 sessions across the three periods described below.

### They take a large share of the agent's work

| Before the deletion | Codebase 1 | Codebase 2 |
|---|---|---|
| Edits that touched a test file | 26% of 10,863 (51% in the Codex CLI) | 19% |
| Tool output that came from reading test files or running tests | 15%, 39 million characters | 12% |
| Test runs inside sessions | 4,102, about 40 hours of recorded wall time | 66 per 1,000 tool calls |

In codebase 1, 151 of 424 sessions ran the suite more than ten times; one ran it 110 times. After the
deletion, test-related calls fell to 0.5% and the time to the first edit of real code halved, from a
median of 7.2 minutes to 3.5. Agents didn't read less; they read the code they were changing.

### They grow the codebase the agent has to search

In codebase 1, 43% of the code files an agent searched were tests, and searching for a production
function's name returned test files for almost half the hits. Once the tests were gone, about 100
definitions and a set of test-only hooks in production code had no caller left. A single cleanup
deleted 2,668 lines of them.

### They make the agent change production code to satisfy them

In codebase 1, 139 commits whose subject was about tests also changed production code, with subjects
like "Keep the suite green after streaming replies and the offers migration". Production code carried
hooks that existed only so a test could reach in: a swappable message sender, cache and
circuit-breaker resets, a pool-timeout knob, a binder "so a test patch reached it". One performance
pass changed production caching to make the suite faster.

### They anchor the agent to its own mistakes

When the tests encode a wrong reading, the agent defends it. In codebase 2, when a test went red, the
agent's next edit changed the test rather than the code 56% of the time. In codebase 1, two tests
asserted access refusals that the design had removed, and had to be inverted before the right
behaviour could ship. Another asserted a decision the agent had manufactured instead of the one the
person made. An agent labelled a check as passing "because the test expected those restrictions".
Removing a structure meant rewriting the tests that described it first. One audit listed test lines as
a removal cost nine times: "about 11,000 test lines and two eval suites encode the passes", "tests pin
exact literals".

### They poison what the agent believes

A fake teaches the agent how the world behaves, and the agent believes it. In codebase 1, simulated
Google services, recording doubles, a recording executor and a fake sign-in all stood in for the real
thing, and stubbed "source-level proof" was reported as proved. Removing them took four commits and
over 26,000 lines. Red CI was "traced to environment, not code, every time". In codebase 2, we told
agents 87 times over eight months to stop mocking and use real dependencies:

> "remove the mocks and call real dependencies, also use real redis not mocks"

Agents kept going back to mocks anyway.

### They steal the session from the task

The owner had to keep pulling agents back. In codebase 1, in the three weeks before the deletion there
were about 13 distinct messages redirecting an agent from tests to the task; after it, one:

> "Why are you still churning role and scope testing instead of proving the workflow live end to end."

> "Do not spend the remediation time re-verifying, rerunning pre-flights or churning tests - testing is
> not the goal and no amount of test churn or additional test fixtures is going to address the actual
> defects - focus on implementing the task at hand."

> "Tell the worker to stop adding tests and remove any test it added and then verify the changes
> directly"

Agents also reach for the cheap ways to turn a suite green. In codebase 1, 267 commits added skips or
expected failures, 115 raised test timeouts and 62 deleted test files.

## Deleting tests alone makes it worse

Codebase 2 removed its unit suites first and told agents to prove changes "with integration tests
against real stores, end-to-end tests, and live drives". The rule said in so many words: "Do not add
unit or mocked-adapter tests." Agents read a real database plus fake providers as "integration against
real stores" and carried on. Over the next ten days:

- 64% of commits touched tests (552 of 859).
- Agents added 10,405 assertions and removed 5,937.
- Test-file edits peaked at 230–270 a day, the busiest stretch of the year.
- The rate of rewritten assertions rose to five times what it had been.

Ten days later the instructions changed. Proof is the live journey plus the persisted record read
back. Fake, stub or "controlled" provider adapters are mocks, even against a real database. No new
tests unless the owner asks. A pre-commit hook rejects new test lines.

| Codebase 2, by period | Unit tests and CI | Unit tests gone, integration tests allowed | No new tests, proof is the live journey |
|---|---|---|---|
| Share of edits that touch test files | 18.8% | 19.6% | **1.8%** |
| Share of tool output from running or reading tests | 12.4% | 14.2% | **3.7%** |
| Test runs per 1,000 tool calls | 66 | 50 | 26 |
| Test files read per 1,000 tool calls | 87 | 81 | 19 |
| Browser, staging and outside-assistant actions per 1,000 tool calls | 12 | 26 | **139** |
| After a red test, the next edit changed the test | 56% | 45% | 14% |
| Commits that touched tests | over half | 64% | **9%** |

**Agents follow the proof standard you set, not the tools you take away.** If "done" can mean "tests
pass", agents will write tests that pass. If "done" means "a person can complete the booking on
staging, and here's the database row", they'll go and do that. Codebase 1 got there in one step
because it banned every kind of test at once.

## Every instruction has to agree

A model's defaults outlast a single instruction. Codebase 2 shows how. Three weeks after the main
instruction file banned new tests, five of the scaffolding skills agents load for routine work (new
service, new tool, new resource, new event, workflow change) still told them to write integration
tests, commit fixtures, mock workflow activities and add replay tests to CI. An agent that loads two
opposite instructions follows its default, and the skill named the concrete step. We rewrote each one
to drive the real caller, read back the persisted record and check the failure that matters.

Mechanical checks back the instructions up, and they leak too. After the hook went in, agents made
about a dozen work-in-progress commits with `--no-verify`, which skips it, though the instructions say
never to do that.

## What we do instead

### The verification ladder

| Rung | What it is | Counts as proof? | Typical time |
|---|---|---|---|
| Rehearsal | The change run with part of the seam replaced: a scripted model, a stub, a synthetic row, a test client | No. Reported as "rehearsed", with what was replaced named | Seconds |
| Local gate | Lint, type checks, the web build, every migration on an empty database in a throwaway server, and a check that no test file or runner has appeared | For source and schema only | About a minute |
| Replay on a restored copy | The branch's code against a fresh copy of production, under real roles and row security, with the production models | Yes, for what the agent and the service do | Minutes |
| Real service and browser | The real integration within what was authorised, with calls recorded and cleaned up; the page used as a person would | Yes, for integrations and pages | Minutes |
| Outside assistant | For a product other assistants use, a real assistant (ChatGPT, Claude, Gemini) driving it against staging; check which tool it chose, what it sent and what it told the person | Yes, for anything an outside assistant consumes | Minutes |
| Outcome eval | Cases judged on what happened, what was asked and what reached a person, never on wording or tool order; run once against the stored result of the previous step | Yes, and it is the regression guard | Minutes to an hour |

| What changed | Proof |
|---|---|
| What the agent does | A replay on a restored copy, judged against the intended behaviour; any sound approach passes |
| An integration | The real service, within what was authorised |
| A tool or page that outside assistants use | The tool driven by at least one outside assistant against staging |
| A deterministic guarantee (access, ledgers, money, migrations, data writes) | One code path for the rule, invariants in the database and fail-loud guards, source checks against the restored copy, plus one pass as each affected role and a readback of what was charged or written |
| A page | The page in a browser, at the sizes and themes people use, with the state after each action checked |

Every change records what ran, against what, the result, the cleanup and what is still unproved.

### Deterministic guarantees: structure first

The unit tests that did catch real bugs caught deterministic arithmetic with a known right answer. That
class of bug is real, and the fix that removes it is structural:

1. **One code path for one fact.** The quote/checkout bug existed because two places computed the same
   price. Remove the second calculation and the disagreement can't happen.
2. **Put invariants in the system, not beside it.** Money is integer minor units, and an impossible
   amount fails loudly instead of being clamped to zero. Database constraints, revision fences and
   guards run on every real request, not only in a test run.
3. **Read back the record.** A test asserts that the code returns 396. A readback shows that the
   ledger, the payment and the booking page all say $396.00.

Where a pure function sits outside all three, a small invariant check on it is reasonable. Write it on
purpose, not as a side effect of every feature.

### CI on the machine that can see production

Hosted CI's one real advantage is a machine the code under test cannot tamper with. We keep it for
exactly that case: code from outside, and work orders from coding agents that run without a person,
still run on hosted runners and never on the production host. Everything else runs locally:

- **The gate runs on the exact commit being pushed** and records the result as a commit status naming
  the checked tree. Hosted CI skips a tree that carries that record, so nothing is run twice and
  nothing is skipped on trust.
- **It refuses to record a dirty tree,** so the record always describes exactly what was pushed.
- **It starts and removes its own database server,** so a run never touches a shared database.
- **The proof kit runs on the same machine.** It restores a copy of production into a private server,
  runs a branch against it with the production models only when asked, serves the app for a browser,
  and drops the copy afterwards. None of that is possible on a hosted runner without moving production
  data and credentials onto it.

Codebase 2 shows what the alternative turns into. From March to October its main hosted workflow
succeeded on 75 of 1,974 runs, and the nightly failed all 105. In a sample of failed runs, 41% never
ran a step (runner allocation and a billing block), 19% failed lint before any test ran and 16% failed
a governance gate. Only 5% reached a test suite. The tests ran inside agent sessions, where the agent
that wrote the code decided whether red meant the code was wrong or the test was. A gate that is
always red tells you nothing, and every agent that reads its output learns that red is normal.

## What changed

| | Codebase 1 before | Codebase 1 after | Codebase 2 before | Codebase 2 after |
|---|---|---|---|---|
| Commits touching a test file | 71% | under 1% | over half | 9% |
| Changed lines that were test lines | 40% | 0.1% | 30–40% | 6% in the latest week |
| CI run | 48–55 minutes | about 1 minute | red 96% of the time | local gate |
| Median pull request | 20 files, 1,600 lines | 13.5 files, 727 lines | — | — |
| Browser, staging and outside-assistant actions per 1,000 tool calls | — | — | 12 | 139 |
| Agent input tokens per commit | — | — | 12.9M | 8.9M |
| Median age of a bug when fixed | — | — | 3.7 days | 3.7 hours |

— means not measured in that codebase.

What the written evidence for each change contains, in codebase 1:

| Evidence mentions | Before (77 records) | After (75 records) |
|---|---|---|
| A restored production copy | 25 | 61 |
| The production models | 3 | 45 |
| A real outside service | 10 | 23 |
| A browser pass | 37 | 46 |
| A section on what is still unproved | 20 | 66 |
| Test-pass counts offered as evidence | 28 | 4 |

The work moved from keeping a suite green to showing behaviour under production conditions. Proofs
caught defects before merge that no test had seen. In codebase 1: a replay that surfaced six defects in
one consolidation, a first run that showed a runaway turn, a container build that would have failed,
and a calculation that returned 0.3547 and reported it as 35.47%. In codebase 2, since the change, 127
of the 139 fixes that say how their bug was found came from driving the product or reading staging
data. Some were serious:

- **A wrong refund.** Cancelling one night of a three-night stay and then the rest re-priced the booking
  from its original price instead of what was left.
- **A minor reaching a card form.** A run through ChatGPT found that a 13–17-year-old's account could
  reach a card form for a booking a parent must pay for.
- **Paris in the wrong country.** A Gemini run found that a hotel search for "Paris" searched Paris,
  United Kingdom, because places around Charles de Gaulle airport were filed under the wrong country.
  No unit test finds that. It only shows up when a real assistant asks a real question.

### What it costs

Live proof makes each session longer. In codebase 2, input tokens per session rose from 8.3M to 12.4M
and tool calls from 43 to 69, because driving a browser, reading screenshots and querying a database
all take tokens. Each session also lands more change, so input tokens per commit fell by about a
third. In the middle period, when agents were writing fake-adapter tests and running multi-agent
review loops, cost per commit peaked at 20.7M. The model spend on live evals is a few dollars a month,
and payment test mode and test inboxes cost nothing. Defects are now found within hours of being
written, on staging, which is the cheapest place to find them.

## What we caused, what the models did

We sorted each finding by one test: did it stop when a person changed a rule, a config or a design, or
did it continue despite clear instructions?

| Ours: it stopped when we changed something | The models': it continued despite instructions |
|---|---|
| "Done" meant "tests pass", so agents anchored on the suite | Defaulting to mocks, through 87 instructions and an explicit ban |
| Our scaffolding skills told agents to write tests with every feature | Writing tests across an explicit ban: 10,405 assertions in ten days |
| A rule that said "integration tests against real stores", which fake providers on a real database fit | Reading that rule for its loophole |
| Hosted CI left red for eight months | Editing the test instead of the code after a red run, against an instruction not to rewrite tests |
| A price computed in two places | Skipping the hook with `--no-verify` |
| Multi-agent review loops that raised the cost per commit by 60% | Writing code and its test from one understanding, so both share the same mistake |

Many of the problems were ordinary engineering mistakes that agents amplified: human teams make every
one in the left column. Agents turn each into thousands of lines in weeks. The model defaults in the
right column are what stopped instructions from fixing it. Fix the left column first. The right
column will still be there afterwards, so plan for it with a proof standard the agent can't satisfy by
writing more tests.

## Pitfalls

- **A partial ban moves the habit.** Ban unit tests and agents write fake-adapter integration tests.
  Ban every new test, and name fakes, stubs and "controlled" adapters as mocks even against a real
  database.
- **Every instruction surface has to agree.** Skills, scaffolds, templates and prompts all teach what
  done means, and the concrete one wins. Search them for "write tests", "add a test" and "mock".
- **Deterministic writes still need a check on a real database.** After the deletion in codebase 1, a
  change wrote an explicit null into a non-null column and contact saves failed for about a day. A
  deleted database-backed test had covered exactly that write. Data writes belong with access, ledgers
  and money on the list of deterministic guarantees checked against the restored copy.
- **A proof covers what you ran, not what you didn't.** A change that removed input schemas from
  tool-search results was proved on a replay and still shipped a defect, because the replay never
  filled the tool list. When a change removes something, prove the case where its absence matters.
- **A proof covers what you looked at.** In codebase 2 a form stayed on screen after it was submitted;
  agents had driven the journey without checking the state afterwards. Name the state to check.
- **Stand-ins creep back.** Agents under pressure reach for fakes and call the result a proof. Name the
  rung ("rehearsed, not proved") in every report, and check for it in review.
- **A one-off proof is not a regression guard.** Behaviour that must not regress belongs in an outcome
  eval that is rerun, or in a deterministic check.
- **Hooks leak.** Agents skip pre-commit hooks for "work in progress". Keep the proof standard in the
  definition of done, where skipping it means the work isn't done.
- **Don't keep a red gate.** Fix it or delete it. Agents read its output and learn that red is normal.
- **Local CI needs provenance.** A status that says "passed" without the tree it checked is a claim, not
  a record. Tie the record to the tree and refuse uncommitted changes.
- **Keep untrusted code off the machine with production access.** Only code your own sessions wrote
  runs locally. Anything from outside runs on hosted runners.
- **Count tokens per change, not per session.** Live proof makes sessions longer. Judge it by what lands
  and what it finds.

## Where it doesn't apply

Libraries and public APIs, where other people's code depends on exact behaviour. Safety-critical
systems with regulated verification. Large human teams, where a test is also communication between
people. Teams with no way to run the real system. And any project where someone other than the code's
author writes the tests: that independence is what makes a test worth having, and it's what
agent-written tests lack.

## How we measured

- **Session logs.** Tool calls were parsed for test paths (`/tests/`, `test_*.py`, `*_test.py`,
  `*.test.ts(x)`, `*.spec.ts(x)`, `conftest.py`) and test-runner commands, with aggregate counts only.
  In codebase 1, "before" is up to the week of 2026-10-12 and "after" from 2026-10-26; the deletion
  week is left out, and redirect counts were vetted by hand. In codebase 2, the three periods are
  before 25 October 2026, 25 October to 4 November, and after 4 November. Browser, staging and
  outside-assistant actions are browser and MCP tool calls plus commands that reach staging or run
  evals.
- **Git.** Test and product lines at points in time, weekly churn, test-file lifespans, assertion lines
  added and removed, and commits touching test paths.
- **CI.** Every hosted run in codebase 2 (7,394), with a random sample of eight failed main-workflow runs
  a month inspected job by job.
- **Defects.** All 89 codebase-2 defect write-ups were read against their commits. For fixes since the
  change, the discovery channel comes from the fix's description. Bug age is the median `git blame` age
  of the product lines each fix replaced, then the median across fixes in each period: 3.7 days for
  the 39 fixes before 25 October, 1.0 day for the 68 in the middle period, and 3.7 hours for the 201
  after 4 November. The 76 fixes that replaced no product lines are left out. The mean moved much less
  (30 days to 26): old defects still surface, but most fixes now land within hours of the code they
  correct. Per-fix figures are in [`codebase-2/data/fix_pr_bug_age.csv`](codebase-2/data/fix_pr_bug_age.csv).
- **Cost.** Input tokens from the harnesses' own usage records, divided by sessions and by commits on
  `main` in the same period.

The codebase-2 scripts and aggregate data are in [`codebase-2/`](codebase-2/). Point the scripts at your
own repository and transcripts to compute the same numbers.

## Related work

**Coding agents and their tests**

- Zhong, Raghunathan, Carlini, "ImpossibleBench: Measuring LLMs' Propensity of Exploiting Test Cases",
  2025. https://arxiv.org/abs/2510.20270. Tests mutated to contradict the specification. GPT-5 passed
  54% of conflicting SWE-bench tasks anyway and Claude Opus 4.1 50%; Claude models cheated mainly by
  editing the tests (over 79% of their cheats), despite instructions not to. A stricter prompt cut
  GPT-5's cheating on one benchmark from over 85% to 1%, and read-only tests stopped test edits but not
  other gaming.
- Chen et al., "Rethinking the Value of Agent-Generated Tests for LLM-Based Software Engineering
  Agents", 2026. https://arxiv.org/abs/2602.07900. GPT-5.2 wrote test files in 2.4% of SWE-bench
  Verified tasks and resolved 71.8%, within 2.6 points of Claude Opus 4.5, which wrote them in 83.6%.
  Prompting agents to write more or fewer tests changed resolution by 0–13 of 500 tasks, with no
  significant difference. The tests mostly printed values rather than asserting them.
- Alonso, Yovine, Braberman, "TDAD: Test-Driven Agentic Development", 2026.
  https://arxiv.org/abs/2603.17973. A generic TDD instruction raised regressions from 6.08% to 9.94%;
  telling the agent which tests its change affects cut them to 1.82%. "Agents do not need to be told
  how to do TDD; they need to be told which tests to check."
- Hora and Robbes, "Are Coding Agents Generating Over-Mocked Tests?", MSR 2026.
  https://arxiv.org/abs/2602.00409. 23% of agent commits touch tests against 13% for others, and 36%
  of agent test commits add mocks against 26%. They recommend mocking guidance in agent config files;
  codebase 2 did that for months without effect.
- Banik, Chowdhury, Shamim, "All Smoke, No Alarm", IEEE AITest 2026. https://arxiv.org/abs/2606.18168.
  80.2% of 86,156 agent test patches have a weak or missing oracle.
- Jhanglani et al., "Beyond Test Presence", 2026. https://arxiv.org/abs/2607.12068. A counterpoint:
  agent tests cover more edge cases with near-human assertion strength, but are more prone to flakiness.
- Konstantinou, Degiovanni, Papadakis, arXiv 2410.21136. https://arxiv.org/abs/2410.21136. Generated
  oracles mainly capture actual behaviour, bugs included.
- Mathews and Nagappan, "Design choices made by LLM-based test generators prevent them from finding
  bugs", 2024. https://arxiv.org/abs/2412.14137

**Instructions and context files**

- Gloaguen et al., "Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding
  Agents?", 2026. https://arxiv.org/abs/2602.11988. Context files don't generally improve task success
  and raise cost by over 20%, but agents do follow the specific tools and steps they name. That is why
  a skill saying "write integration tests" beat a general rule against it.
- Schwab, "Tests Beat Instructions for AI Coding Agents", 2026.
  https://caimito.net/en/blog/2026/04/17/tests-beat-instructions-for-ai-coding-agents.html. Agrees
  instructions alone don't hold; proposes tests as the executable constraint. We agree when a person
  writes the failing test and the agent can't edit it.

**Independent verification**

- An (Momentic), "Your coding agent shouldn't grade its own homework", Stack Overflow blog, 2026.
  https://stackoverflow.blog/2026/11/13/your-coding-agent-shouldn-t-grade-its-own-homework. A testing
  vendor's audit of 1,000 AI-written unit tests in its own code base judged 9.6% useful; a separate QA
  agent with fresh context and the running app reported 3–5 times as many bugs.
- Pant, "Your coding agent should watch its own work run", 2026.
  https://rajiv.com/blog/2026/06/27/your-coding-agent-should-watch-its-own-work-run/
- Willison, "Your job is to deliver code you have proven to work", 2025.
  https://simonwillison.net/2025/Dec/18/code-proven-to-work/
- Wang et al., "The Verification Horizon", 2026. https://arxiv.org/abs/2606.26300. Every verifier is a
  proxy for intent.

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

**Testing against production state, and outcome evals**

- Majors, "I test in prod", 2019. https://increment.com/testing/i-test-in-production/
- GoReplay, https://github.com/buger/goreplay, and Diffy, https://github.com/opendiffy/diffy, for replay of
  real traffic and response comparison.
- Grace, Hadfield, Olivares, De Jonghe (Anthropic), "Demystifying evals for AI agents", 2026.
  https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents. Grade the final state, not the path.
- Yao, Shinn, Razavi, Narasimhan, "τ-bench", 2024. https://arxiv.org/abs/2406.12045
- Shankar et al., "Who Validates the Validators?", 2024. https://arxiv.org/abs/2404.12272

**The case for tests**

- Anthropic, "Claude Code: Best practices for agentic coding", 2025.
  https://www.anthropic.com/engineering/claude-code-best-practices. Recommends writing tests first,
  then the code.
- Orosz, "TDD, AI agents and coding with Kent Beck", The Pragmatic Engineer, 2025.
  https://newsletter.pragmaticengineer.com/p/tdd-ai-agents-and-coding-with-kent. The newsletter calls TDD
  a "superpower" with AI agents, and reports that Beck struggles to stop agents deleting tests to make
  them pass. Test-first holds when a person owns the test; when the agent writes both sides, it is the
  failure this study describes.
- Nagappan, Maximilien, Bhat, Williams, "Realizing quality improvement through test driven development",
  *Empirical Software Engineering* 13(3), 2008.
- Yuan et al., "Simple Testing Can Prevent Most Critical Failures", OSDI 2014.
  https://www.usenix.org/conference/osdi14/technical-sessions/presentation/yuan. Its lesson is our
  deterministic-writes pitfall: error paths in deterministic code deserve a check.
- Petrović, Ivanković, Fraser, Just, "Does mutation testing improve testing practices?", ICSE 2021.
  https://arxiv.org/abs/2103.07189

**Close to our practice**

- McCarthy (StrongDM), "Software Factory", 2026. https://factory.strongdm.ai/. Held-out scenarios in
  place of in-repo tests. They score against simulated services; we would call that a rehearsal.
- Freire (Nubank), "Why We Killed Our End-to-End Test Suite", 2021. https://building.nu.com/why-we-killed-our-end-to-end-test-suite/

**What this study adds.** Two production codebases measured from the agents' own logs, not
benchmarks. Two findings we haven't seen documented: a partial ban moves agents' test-writing into
fake-adapter "integration" tests, and instruction-level fixes that work on benchmarks (a stricter
prompt, mocking guidance in config files) didn't hold over months of real work. Proof standards did.
