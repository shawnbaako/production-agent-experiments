# Codebase 2: scripts and aggregate data

`data/` holds the aggregates behind the codebase-2 numbers in the study: weekly test and product churn,
CI results and billing by month, a sample of failed CI jobs, agent activity by period, and the age of
the code each fix replaced. Raw session logs and prompts are not published.

To compute the same numbers for your own repository and coding-agent sessions:

```bash
export PROJECT_FILTER='my-repo'                                          # regex matching your checkout path(s)
python3 scripts/git_metrics.py /path/to/repo > data/git_weekly.csv     # weekly test vs product churn
scripts/test_lifecycle.sh /path/to/repo                                 # test-file lifespans, assertion churn
scripts/ci_runs.sh OWNER/REPO                                           # every Actions run + failed-job sample
python3 scripts/extract_events.py > data/events.jsonl                  # Claude Code, Codex, pi sessions -> one event stream
python3 scripts/analyze_events.py data/events.jsonl                    # test vs live-product work by period
python3 scripts/bug_origin.py /path/to/repo data/prs_merged.jsonl      # how old was the code each fix PR replaced
python3 scripts/prompt_patterns.py                                      # mock and pushback prompts by month
python3 scripts/fix_discovery.py                                        # how each fix says its bug was found
```

The period boundaries and test-path patterns are constants at the top of each script; change them to
match your repository. `extract_events.py` reads each harness's default session location under your
home directory. `analyze_events.py` counts browser and staging actions with the patterns in `LIVE_CMD`
and `LIVE_MCP`, so add your own staging hosts there. `bug_origin.py` expects merged pull requests as
JSON lines with `number`, `title`, `merged_at` and `head`, for example from
`gh api "repos/OWNER/REPO/pulls?state=closed&per_page=100" --paginate`.
