#!/usr/bin/env bash
# Test-file lifespans and monthly assertion churn on origin/main. Usage: test_lifecycle.sh REPO
set -euo pipefail
cd "$1"
git log origin/main --no-merges --diff-filter=AD --name-status --format='@@%aI' | python3 -c '
import sys,re,statistics as st,datetime as dt
T=re.compile(r"(^|/)(tests?|__tests__|integration_test)/|(^|/)test_[^/]*\.py$|_test\.(py|dart)$|\.(spec|test)\.(ts|js)$")
rows=[];cur=None
for l in sys.stdin:
    l=l.rstrip("\n")
    if l.startswith("@@"): cur=l[2:]; continue
    if l and cur and T.search(l.split("\t")[-1]): rows.append((cur,l.split("\t")[0],l.split("\t")[-1]))
rows.sort(); add={}; life=[]; bulk=0
for t,s,p in rows:
    if s=="A": add[p]=t
    elif s=="D" and p in add:
        if t.startswith("2026-10-25"): bulk+=1; continue
        life.append((dt.datetime.fromisoformat(t)-dt.datetime.fromisoformat(add.pop(p))).total_seconds()/86400)
print("created",sum(r[1]=="A" for r in rows),"deleted",len(life),"cutover-day",bulk,
      "median_days %.1f"%st.median(life),"under7d %.0f%%"%(100*sum(x<7 for x in life)/len(life)))'
git log origin/main --no-merges -p --format='@@%ad' --date=format:%Y-%m -- tests '*test_*.py' '*_test.dart' '*.spec.ts' | python3 -c '
import sys,re,collections
c=collections.defaultdict(collections.Counter);m=None
for l in sys.stdin:
    if l.startswith("@@") and not l.startswith("@@ "): m=l[2:9]; continue
    if re.match(r"^-\s*(assert |self\.assert|expect\()",l): c[m]["removed"]+=1
    elif re.match(r"^\+\s*(assert |self\.assert|expect\()",l): c[m]["added"]+=1
for k in sorted(c): print(k,dict(c[k]))'
