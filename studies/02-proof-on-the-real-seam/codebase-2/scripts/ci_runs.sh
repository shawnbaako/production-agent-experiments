#!/usr/bin/env bash
# Download every Actions run and a sample of failed main-CI jobs. Usage: ci_runs.sh OWNER/REPO
set -euo pipefail
R=$1
gh api "repos/$R/actions/runs?per_page=100" --paginate \
  --jq '.workflow_runs[]|{id,name,path,event,status,conclusion,created_at,run_started_at,updated_at,head_sha,run_attempt}' > data/gh_runs.jsonl
python3 -c '
import json,random,collections
by=collections.defaultdict(list)
for r in map(json.loads,open("data/gh_runs.jsonl")):
    if r["path"].endswith("ci.yml") and r["conclusion"]=="failure": by[r["created_at"][:7]].append(r["id"])
random.seed(7)
for m,ids in sorted(by.items()):
    for i in random.sample(ids,min(8,len(ids))): print(m,i)' > data/ci_sample_ids.txt
while read -r m id; do
  gh api "repos/$R/actions/runs/$id/jobs" --jq "\"$m $id \"+([.jobs[]|\"\(.name)=\(.conclusion)[\([.steps[]?|select(.conclusion==\"failure\")|.name]|join(\",\"))] ok_steps=\([.steps[]?|select(.conclusion==\"success\")]|length)\"]|join(\" | \"))"
done < data/ci_sample_ids.txt > data/ci_sample_jobs.txt
