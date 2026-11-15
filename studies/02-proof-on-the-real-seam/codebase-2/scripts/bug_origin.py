"""For each merged fix PR, find when the product lines it replaced were written (git blame).

A fix that changes lines written before the unit-test removal is fixing a defect that shipped
under the unit-test regime; one that changes lines written after it is fixing newer code.

Usage: python3 bug_origin.py REPO data/prs_merged.jsonl > data/bug_origin.jsonl
"""

import json
import re
import subprocess
import sys
from collections import Counter

REPO, PRS = sys.argv[1], sys.argv[2]
CUTOVER = "2026-10-25T17:12"
PROD = re.compile(r"^platform/.*\.(py|ts|tsx|astro|j2|sql)$")
TEST = re.compile(r"(^|/)tests?/|test_[^/]*\.py$|\.spec\.ts$|/checks/")


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True).stdout


merges = {}
for line in git("log", "origin/main", "--first-parent", "--merges", "--format=%H %s").splitlines():
    m = re.search(r"Merge pull request #(\d+)", line)
    if m:
        merges[int(m.group(1))] = line.split()[0]

prs = [json.loads(l) for l in open(PRS) if l.startswith("{")]
for p in prs:
    if not (
        re.match(r"(fix|repair|restore|correct)", p["title"], re.I) or p["head"].startswith("fix/")
    ):
        continue
    sha = merges.get(p["number"])
    if not sha:
        continue
    ages = Counter()
    line_times = []
    diff = git("diff", "--unified=0", f"{sha}^1", sha)
    path = None
    for dl in diff.splitlines():
        if dl.startswith("--- a/"):
            path = dl[6:]
        elif dl.startswith("--- /dev/null"):
            path = None
        elif dl.startswith("@@") and path and PROD.search(path) and not TEST.search(path):
            m = re.match(r"@@ -(\d+)(?:,(\d+))?", dl)
            start, n = int(m.group(1)), int(m.group(2) or 1)
            if n == 0:
                continue
            blame = git(
                "blame", "--line-porcelain", "-L", f"{start},+{min(n, 200)}", f"{sha}^1", "--", path
            )
            for bl in blame.splitlines():
                if bl.startswith("author-time "):
                    import datetime

                    t = datetime.datetime.utcfromtimestamp(int(bl.split()[1])).isoformat()
                    ages["pre" if t < CUTOVER else "post"] += 1
                    line_times.append(t)
    total = ages["pre"] + ages["post"]
    print(
        json.dumps(
            {
                "pr": p["number"],
                "merged": p["merged_at"],
                "title": p["title"],
                "replaced_lines": total,
                "pre_cutover_lines": ages["pre"],
                "post_cutover_lines": ages["post"],
                "median_line_written": sorted(line_times)[len(line_times) // 2]
                if line_times
                else None,
            }
        )
    )
