#!/usr/bin/env python3
"""Fixed workflows against one agent with the same tools, on an operations inbox.

Arms (one file each):
  workflow         workflow.py   fixed steps; the model classifies, extracts fields and writes reply text
  guards           guards.py     the workflow plus the usual patches: dedupe, clash check, cap, fallbacks
  agent            agent.py      one tool-calling loop; money arithmetic and the approval boundary in the tools
  agent_machinery  machinery.py  the agent with a call cap, a repeat guard, one use per writing tool, a scope rule
  agent_bare       bare.py       the agent with the exact parts taken out of the tools and put in the brief

  OPENROUTER_API_KEY=... python3 run.py run --model deepseek/deepseek-v4.1-flash
  python3 run.py report

Every model response is cached in results/calls/<model>.jsonl under a hash of the exact request and the
repeat index. `report` replays every run from the cache through the same code without a network call and
writes results/report.json. Standard library only.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import sys
import tokenize
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cases as C  # noqa: E402
import llm  # noqa: E402
from agent import Agent  # noqa: E402
from bare import Bare  # noqa: E402
from guards import Guarded  # noqa: E402
from machinery import Machinery  # noqa: E402
from workflow import Workflow  # noqa: E402

ARMS = {"workflow": Workflow, "guards": Guarded, "agent": Agent, "agent_machinery": Machinery, "agent_bare": Bare}
FILES = {"workflow": ["workflow.py"], "guards": ["workflow.py", "guards.py"], "agent": ["agent.py"],
         "agent_machinery": ["agent.py", "machinery.py"], "agent_bare": ["agent.py", "bare.py"]}
GROUPS = ("script", "variation", "exact")
RESULTS = HERE / "results"


def run_one(arm: str, task: dict, rep: int, cache: llm.Cache) -> dict:
    w0 = C.world_for(task)
    w = json.loads(json.dumps(w0))
    ctx = llm.Ctx(cache, rep)
    a = ARMS[arm](ctx, w)
    try:
        res = a.run(task["message"])
    except llm.Offline:
        return {"arm": arm, "task": task["id"], "rep": rep, "status": "incomplete"}
    chk = C.check(task, w0, w, res["status"] == "handed_back")
    chk["strict_outcome"] = C.check(task, w0, w, res["status"] == "handed_back", strict=True)["outcome"]
    return {"arm": arm, "task": task["id"], "group": task["group"], "rep": rep, "status": res["status"],
            "note": res.get("note") or res.get("reason") or "", **chk, "model_calls": ctx.calls,
            "tool_calls": len(a.log), "failed_tool_calls": sum(not x["ok"] for x in a.log),
            "prompt_tokens": ctx.prompt_tokens, "cost": ctx.cost}


def run(args) -> int:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    cache = llm.Cache(args.model, key, args.max_cost)
    arms = args.arms.split(",") if args.arms else list(ARMS)
    tasks = [t for t in C.TASKS if not args.tasks or t["id"] in args.tasks.split(",")]
    jobs = [(a, t, r) for r in range(args.reps) for a in arms for t in tasks]
    print(f"{args.model}: {len(jobs)} runs; ${cache.spent:.4f} spent so far in all (cap ${args.max_cost})")
    with ThreadPoolExecutor(args.workers) as ex:
        out = list(ex.map(lambda j: run_one(*j, cache), jobs))
    print(Counter(o["status"] for o in out), f"${cache.spent:.4f} spent in all")
    for o in out:
        if args.verbose and o["status"] != "incomplete":
            print(o["arm"], o["task"], o["rep"], o["outcome"], o["missing"], o["wrong"], o["note"][:100])
    return 0


# ── report ───────────────────────────────────────────────────────────────

def code_lines(path: Path, only: set[str] | None = None) -> int:
    """Lines holding code: no blanks, comments or docstrings. `only` limits it to these top-level functions."""
    src = path.read_text()
    keep = None
    if only:
        keep = set()
        for n in ast.parse(src).body:
            if isinstance(n, ast.FunctionDef) and n.name in only:
                keep |= set(range(n.lineno, n.end_lineno + 1))
    lines, prev = set(), tokenize.NEWLINE
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                        tokenize.ENDMARKER):
            if tok.type in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
                prev = tok.type
            continue
        if tok.type == tokenize.STRING and prev in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            prev = tokenize.STRING
            continue
        prev = tok.type
        lines |= set(range(tok.start[0], tok.end[0] + 1))
    return len(lines if keep is None else lines & keep)


def loc() -> dict:
    out = {arm: sum(code_lines(HERE / f) for f in files) for arm, files in FILES.items()}
    out["shared_tools(world.py)"] = code_lines(HERE / "world.py")
    out["hard_code_in_tools"] = code_lines(HERE / "world.py", {"create_invoice", "split_invoice", "_reissue",
                                                               "draft_reply"})
    return out


def _agg(rs: list[dict]) -> dict:
    n = len(rs)
    oc = Counter(r["outcome"] for r in rs)
    return {"runs": n, "correct": oc["correct"], "correct_strict": sum(r["strict_outcome"] == "correct" for r in rs),
            "extra_tasks": sum(r["extra_tasks"] for r in rs), "wrong": oc["wrong"], "handed_back": oc["handed_back"],
            "missed": oc["missed"], "runs_handing_back": sum(r["handed_back"] for r in rs),
            "wrong_actions": sum(len(r["wrong"]) for r in rs), "duplicates": sum(r["duplicates"] for r in rs),
            "sent_without_approval": sum(any(w.startswith("sent mail") for w in r["wrong"]) for r in rs),
            "model_calls_per_run": round(sum(r["model_calls"] for r in rs) / n, 2),
            "tool_calls_per_run": round(sum(r["tool_calls"] for r in rs) / n, 2),
            "prompt_tokens_per_run": round(sum(r["prompt_tokens"] for r in rs) / n),
            "cost_per_run": round(sum(r["cost"] for r in rs) / n, 5), "cost": round(sum(r["cost"] for r in rs), 4)}


def report(_args) -> int:
    full: dict = {"loc": loc(), "models": {}}
    for p in sorted(llm.CALLS.glob("*.jsonl")):
        model = json.loads(p.read_text().splitlines()[0])["model"]
        cache = llm.Cache(model, None, 0)
        reps = 3
        runs = [run_one(a, t, r, cache) for a in ARMS for t in C.TASKS for r in range(reps)]
        runs = [r for r in runs if r["status"] != "incomplete"]
        if not runs:
            continue
        m: dict = {"arms": {}, "per_task": defaultdict(dict), "cached_calls": len(cache.rows),
                   "cost_usd": round(sum(r["cost"] for r in cache.rows.values()), 4),
                   "providers": dict(Counter(r.get("provider") for r in cache.rows.values()))}
        for arm in ARMS:
            ra = [r for r in runs if r["arm"] == arm]
            if not ra:
                continue
            m["arms"][arm] = {"all": _agg(ra), **{g: _agg([r for r in ra if r["group"] == g])
                                                  for g in GROUPS if any(r["group"] == g for r in ra)}}
            for t in C.TASKS:
                rt = [r for r in ra if r["task"] == t["id"]]
                if rt:
                    m["per_task"][arm][t["id"]] = [{k: r[k] for k in ("outcome", "missing", "wrong", "status", "note")}
                                                   for r in rt]
        full["models"][p.stem] = m
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "report.json").write_text(json.dumps(full, indent=1, sort_keys=True) + "\n")
    print("| model | arm | on-script | variations | exact | wrong actions | hand-backs | duplicates | "
          "model calls per task | cost per task | correct, strict |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for model, m in full["models"].items():
        for arm, q in m["arms"].items():
            g = {k: (f"{q[k]['correct']}/{q[k]['runs']}" if k in q else "-") for k in GROUPS}
            a = q["all"]
            print(f"| {model} | {arm} | {g['script']} | {g['variation']} | {g['exact']} | {a['wrong_actions']} | "
                  f"{a['runs_handing_back']} | {a['duplicates']} | {a['model_calls_per_run']} | ${a['cost_per_run']:.4f} | {a['correct_strict']}/{a['runs']} |")
    print("\nper task, correct out of runs:")
    for model, m in full["models"].items():
        print(f"\n{model}\n| task | " + " | ".join(m["arms"]) + " |")
        for t in C.TASKS:
            cells = []
            for arm in m["arms"]:
                rs = m["per_task"][arm].get(t["id"], [])
                cells.append(f"{sum(r['outcome'] == 'correct' for r in rs)}/{len(rs)}" if rs else "-")
            print(f"| {t['id']} | " + " | ".join(cells) + " |")
    print("\nlines of code:", json.dumps(full["loc"]))
    total = sum(m["cost_usd"] for m in full["models"].values())
    print(f"{sum(m['cached_calls'] for m in full['models'].values())} cached calls, ${total:.4f} in all")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--model", required=True)
    r.add_argument("--reps", type=int, default=3)
    r.add_argument("--arms")
    r.add_argument("--tasks")
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--verbose", action="store_true")
    r.add_argument("--max-cost", type=float, default=3.0, help="stop when every cached call together costs this")
    r.set_defaults(fn=run)
    sub.add_parser("report").set_defaults(fn=report)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
