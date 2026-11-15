"""Classify how each post-cutover fix PR says its bug was found (keyword match on the PR body).

Input: data/bc_fix_bodies.jsonl, one {number,title,merged_at,body} per line, from
  gh api repos/OWNER/REPO/pulls/N --jq '{number,title,merged_at,body}|tojson'
for every PR in data/bug_origin.jsonl merged after the cutover.
"""
import collections, json, re

CH = [("external assistant run", r"\b(chatgpt|claude\.ai|gemini|connector)\b.{0,80}(run|journey|drive|found|turn)|(live|found|run).{0,40}(chatgpt|claude\.ai|gemini)"),
      ("staging drive / deployed build", r"staging (run|drive|journey|build)|deployed build|on staging|found (live|on staging)|driving|drove|live (run|drive|journey)|browser|playwright|screenshot|png"),
      ("independent review", r"\breview(er)?\b.{0,40}(found|turned up|flagged)|final review|code review"),
      ("reported by a person", r"\b(founder|user|customer|reported by)\b.{0,40}(found|report|saw|noticed|asked)"),
      ("test", r"(integration|e2e|existing) test.{0,30}(caught|found|failed)|test caught"),
      ("staging data / logs", r"\blogs?\b|glitchtip|sentry|rows?\b.{0,20}(open|stuck)|readback")]
c = collections.defaultdict(collections.Counter)
for r in map(json.loads, open("data/bc_fix_bodies.jsonl")):
    b = (r["title"] + " " + (r["body"] or "")).lower()
    ph = "B" if r["merged_at"] < "2026-11-04T15:09" else "C"
    c[ph][next((k for k, p in CH if re.search(p, b)), "not stated")] += 1
for ph in sorted(c):
    print(ph, dict(c[ph].most_common()))
