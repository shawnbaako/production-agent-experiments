"""Classify transcript events and compare before/after the unit-test removal (2026-10-25 17:12Z).

Usage: python3 analyze_events.py data/events.jsonl > data/events_summary.json
"""

import collections
import json
import os
import re
import sys

CUTOVER = "2026-10-25T17:12"
TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|test_driver|integration_test)/|(^|/)test_[^/]*\.py$|_test\.(py|dart)$"
    r"|\.(spec|test)\.(ts|tsx|js|mjs)$|(^|/)conftest\.py$"
)
UNIT_PATH = re.compile(r"tests/(platform/)?unit/|/test/.*_test\.dart|tests/ci/")
TEST_RUN = re.compile(
    r"\bpytest\b|flutter test|dart test|\bvitest\b|\bjest\b|npm (run )?test|playwright test|make test"
    r"|test:browser|test:live|test:unit"
)
UNIT_RUN = re.compile(r"tests/(platform/)?unit|flutter test|test:unit|-m unit|tests/ci")
LIVE_CMD = re.compile(
    r"staging|run_journey|evals|psql|alembic current"  # add your own staging hosts and eval runners
    r"|stripe |playwright(?! test)|chromium|screenshot|curl .*(localhost|127\.0\.0\.1):\d+"
)
LIVE_MCP = re.compile(os.environ.get("LIVE_MCP", r"playwright|stripe|cua_repl|browser|staging"))
BASH_TEST_EDIT = re.compile(r"(sed -i|cat >|tee |>>?)\s*[^|;&]*(tests?/|test_\w+\.py|\.spec\.ts)")

SKIP = re.compile(r"pytest\.skip|mark\.skip|xfail|\.skip\(|test\.fixme|@unittest\.skip")
MOCK = re.compile(
    r"\bMock\b|MagicMock|AsyncMock|monkeypatch|mock\.patch|@patch|unittest\.mock|vi\.mock|jest\.mock|FakeClient|Fake[A-Z]\w+|Stub[A-Z]"
)
ASSERT = re.compile(r"^\s*(assert |self\.assert|expect\()", re.M)


RULE = "2026-11-04T15:09"  # 290f1d676: no new tests, fakes are mocks, pre-commit hook


def window(ts: str) -> str:
    if ts < CUTOVER:
        return "A_unit+ci"
    return "B_integration" if ts < RULE else "C_live_proof"


def main(path):
    rows = [json.loads(l) for l in open(path)]
    rows = [r for r in rows if r.get("ts") and r["ts"] >= "2026-10-01"]
    rows.sort(key=lambda r: (r["harness"], r["session"], r["ts"]))

    S = collections.defaultdict(collections.Counter)  # (window, harness) -> counters
    sessions = collections.defaultdict(set)
    last_fail = {}  # session -> ts of last failing test run with no edit since
    examples = collections.defaultdict(list)

    for r in rows:
        w, h = window(r["ts"]), r["harness"]
        k = (w, h)
        c = S[k]
        sessions[k].add(r["session"])
        kind = r["kind"]
        if kind == "usage":
            c["tokens_in"] += r.get("tokens_in", 0)
            c["tokens_out"] += r.get("tokens_out", 0)
            c["model_calls"] += 1
            continue
        if kind == "user":
            c["user_msgs"] += 1
            continue
        c["tool_calls"] += 1
        out = r.get("out_chars", 0)
        c["out_chars"] += out
        tgt = r.get("target") or ""
        if kind == "cmd":
            c["cmds"] += 1
            if TEST_RUN.search(tgt):
                c["test_runs"] += 1
                c["test_run_out_chars"] += out
                if UNIT_RUN.search(tgt):
                    c["unit_runs"] += 1
                failed = r.get("failed", 0) + r.get("errors", 0)
                if failed:
                    c["test_runs_failed"] += 1
                    last_fail[r["session"]] = r
                if r.get("passed") is not None and not failed:
                    c["test_runs_green"] += 1
            elif LIVE_CMD.search(tgt):
                c["live_cmds"] += 1
            if BASH_TEST_EDIT.search(tgt):
                c["bash_test_edits"] += 1
            if re.search(r"--no-verify|NEW_TEST_APPROVED", tgt):
                c["gate_bypass_attempts"] += 1
            if re.search(r"(cat|sed -n|head|tail|less|rg|grep)\b[^|]*tests?/", tgt):
                c["test_reads"] += 1
                c["test_read_out_chars"] += out
        elif kind == "read":
            if TEST_PATH.search(tgt):
                c["test_reads"] += 1
                c["test_read_out_chars"] += out
        elif kind == "mcp":
            if LIVE_MCP.search(r.get("name", "")):
                c["live_mcp"] += 1
        elif kind == "edit":
            c["edits"] += 1
            is_test = bool(TEST_PATH.search(tgt))
            plus, minus = r.get("plus", ""), r.get("minus", "")
            # repair direction: first edit after a failing test run
            lf = last_fail.pop(r["session"], None)
            if lf is not None:
                c["post_fail_edit_test" if is_test else "post_fail_edit_prod"] += 1
                if is_test and len(examples[(w, "bent_test")]) < 40:
                    examples[(w, "bent_test")].append(
                        {
                            "harness": h,
                            "session": r["session"],
                            "ts": r["ts"],
                            "path": tgt,
                            "after_cmd": lf.get("target", "")[:200],
                        }
                    )
            if is_test:
                c["test_edits"] += 1
                if UNIT_PATH.search(tgt):
                    c["unit_test_edits"] += 1
                c["test_lines_plus"] += plus.count("\n") + 1 if plus else 0
                if r.get("write"):
                    c["test_files_written"] += 1
                if len(SKIP.findall(plus)) > len(SKIP.findall(minus)):
                    c["sig_added_skip"] += 1
                    examples[(w, "skip")].append(
                        {"session": r["session"], "path": tgt, "harness": h}
                    )
                if len(MOCK.findall(plus)) > len(MOCK.findall(minus)):
                    c["sig_added_mock"] += 1
                na, nm = len(ASSERT.findall(plus)), len(ASSERT.findall(minus))
                if nm and na and plus != minus:
                    c["sig_assert_rewritten"] += 1
                if nm > na:
                    c["sig_asserts_removed"] += 1
            else:
                c["prod_edits"] += 1

    out = {}
    for k, c in sorted(S.items()):
        c["sessions"] = len(sessions[k])
        out["/".join(k)] = dict(c)
    out["examples"] = {"/".join(k): v[:15] for k, v in examples.items()}
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
