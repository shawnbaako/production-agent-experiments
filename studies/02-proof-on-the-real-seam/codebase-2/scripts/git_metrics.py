"""Weekly churn split into test vs product code, from git numstat on origin/main.

Usage: python3 git_metrics.py /path/to/repo > data/git_weekly.csv
Also writes data/git_commits.jsonl (one row per non-merge commit).
"""

import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date

REPO = sys.argv[1]
TEST_RE = re.compile(
    r"(^|/)(tests?|__tests__|test_driver|integration_test)/|(^|/)test_[^/]*\.py$|_test\.(py|dart|go)$"
    r"|\.(spec|test)\.(ts|tsx|js|mjs)$|(^|/)conftest\.py$|(^|/)checks/"
)
GENERATED_RE = re.compile(
    r"(\.lock$|lock\.json$|\.g\.dart$|\.freezed\.dart$|\.min\.|/fixtures?/.*\.(json|ya?ml)$|\.snap$)"
)
CODE_EXT = re.compile(r"\.(py|ts|tsx|js|mjs|dart|astro|sql|j2|go|rs)$")

out = subprocess.run(
    [
        "git",
        "-C",
        REPO,
        "log",
        "origin/main",
        "--no-merges",
        "--numstat",
        "--date=short",
        "--format=@@%H\t%ad\t%an\t%s",
    ],
    capture_output=True,
    text=True,
    check=True,
).stdout

commits = []
cur = None
for line in out.splitlines():
    if line.startswith("@@"):
        sha, d, author, subj = line[2:].split("\t", 3)
        cur = {
            "sha": sha,
            "date": d,
            "author": author,
            "subject": subj,
            "test_add": 0,
            "test_del": 0,
            "prod_add": 0,
            "prod_del": 0,
            "test_files": 0,
            "prod_files": 0,
            "fixture_add": 0,
        }
        commits.append(cur)
    elif line.strip() and cur is not None:
        a, d, path = line.split("\t", 2)
        if a == "-":
            continue
        a, d = int(a), int(d)
        if GENERATED_RE.search(path):
            if TEST_RE.search(path):
                cur["fixture_add"] += a
            continue
        if TEST_RE.search(path):
            cur["test_add"] += a
            cur["test_del"] += d
            cur["test_files"] += 1
        elif CODE_EXT.search(path):
            cur["prod_add"] += a
            cur["prod_del"] += d
            cur["prod_files"] += 1

with open("data/git_commits.jsonl", "w") as f:
    for c in commits:
        f.write(json.dumps(c) + "\n")

weeks = defaultdict(lambda: defaultdict(int))
for c in commits:
    y, w, _ = date.fromisoformat(c["date"]).isocalendar()
    k = f"{y}-W{w:02d}"
    wk = weeks[k]
    wk["commits"] += 1
    for f_ in ("test_add", "test_del", "prod_add", "prod_del"):
        wk[f_] += c[f_]
    if c["test_files"] and not c["prod_files"]:
        wk["test_only_commits"] += 1
    if c["test_files"] and c["prod_files"]:
        wk["mixed_commits"] += 1
    if c["prod_files"] and not c["test_files"]:
        wk["prod_only_commits"] += 1

w = csv.writer(sys.stdout)
cols = [
    "commits",
    "prod_only_commits",
    "test_only_commits",
    "mixed_commits",
    "prod_add",
    "prod_del",
    "test_add",
    "test_del",
]
w.writerow(["week"] + cols + ["test_share_of_churn"])
for k in sorted(weeks):
    wk = weeks[k]
    tc = wk["test_add"] + wk["test_del"]
    pc = wk["prod_add"] + wk["prod_del"]
    w.writerow([k] + [wk[c] for c in cols] + [round(tc / (tc + pc), 3) if tc + pc else ""])
