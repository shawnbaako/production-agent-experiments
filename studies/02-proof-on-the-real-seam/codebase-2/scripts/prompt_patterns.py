"""Monthly counts of your prompts about mocks and of pushback prompts (Claude + Codex history).

Prints counts only; prompt text stays local. Usage: PROJECT_FILTER=myrepo python3 prompt_patterns.py
"""
import collections, datetime, json, os, re

H = os.path.expanduser("~")
MOCK = r"\bmock(s|ed|ing)?\b|\bfake (adapter|provider|client)|\bstub"
PUSH = (r"still (broken|failing|not|doesn'?t|wrong|missing|shows?)|not fixed|you (said|claimed|reported)"
        r"|didn'?t (work|fix)|doesn'?t work|is broken|regress|why (is|did|are) (it|this|the|you)"
        r"|that'?s (wrong|not)|wasn'?t (fixed|done)|you (didn'?t|did not|never)|again\?|same (issue|bug|problem|error)")
rows = [(r["timestamp"] / 1000, r["display"]) for r in map(json.loads, open(f"{H}/.claude/history.jsonl"))
        if re.search(os.environ["PROJECT_FILTER"], r.get("project") or "") and r.get("display")]
if os.path.exists(f"{H}/.codex/history.jsonl"):
    rows += [(r.get("ts"), r.get("text", "")) for r in map(json.loads, open(f"{H}/.codex/history.jsonl"))]
c = collections.defaultdict(collections.Counter)
for ts, t in rows:
    if not ts:
        continue
    d = datetime.datetime.fromtimestamp(ts)
    ph = "A" if d < datetime.datetime(2026, 10, 25, 13) else ("B" if d < datetime.datetime(2026, 11, 4, 10) else "C")
    for k in (d.strftime("%Y-%m"), "phase " + ph):
        c[k]["prompts"] += 1
        c[k]["mock"] += bool(re.search(MOCK, t, re.I))
        c[k]["pushback"] += bool(re.search(PUSH, t, re.I))
for k in sorted(c):
    print(k, dict(c[k]))
