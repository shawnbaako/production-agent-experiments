#!/usr/bin/env python3
"""How the shape of a tool-search result steers an agent loop.

A minimal agent loop on a synthetic catalogue (catalogue.py: 100 invented business tools, 20 tasks).
The model sees six primary tools with their schemas, plus find_tools (search the catalogue) and
run_tool (run a catalogue tool by name). Only what find_tools returns changes between conditions:

Every search returns the five closest tools, as an embedding search would, never an empty list.

  names    the closest tools, name and description only
  schemas  the closest tools, with their input schemas
  plain    as `schemas`, and the result says plainly that there is no further page and that, if
           none of these fits, no tool here does it; a tool name that does not exist is answered
           "No tool is named X."
  paged    as `schemas`, and the result says "Less close matches follow with the same query and
           offset=N"; offsets page through a ranking of the whole catalogue

The search itself (BM25 over names, descriptions and argument names) is the same in every condition.
run_tool validates arguments against the schema and answers with what is wrong, as a JSON-schema
validator would; a valid call succeeds with a synthetic result.

  OPENROUTER_API_KEY=... python3 agent.py run --label deepseek-v4.1-flash --model deepseek/deepseek-v4.1-flash
  python3 agent.py report

Every model response is cached in results/<label>.jsonl, keyed by condition, task, repeat and step,
with a hash of the request it answered. `report` replays every run from the cache through the same
loop, without a network call, and writes results/report.json. Failed calls are not cached; a run that
fails part-way resumes from its cached steps. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import catalogue as C  # noqa: E402

RESULTS = HERE / "results"
CONDITIONS = ("names", "schemas", "plain", "paged")
PAGE = 5
MAX_STEPS = 16

SYSTEM = (f"You are the operations assistant for {C.FIRM}, a consulting firm. Today is {C.TODAY}. You act for "
          "the person writing to you, with their full access. A few tools are listed directly. Many more are in "
          "the firm's tool catalogue: search it with find_tools and run what you find with run_tool. When you are "
          "finished, answer the person in one short message that starts with DONE: if you did what they asked, "
          "or CANNOT: if it cannot be done with the tools here.")

FIND_TOOLS = {"name": "find_tools", "description": "Search the firm's tool catalogue by what you want to do, or by "
              "a tool's name.",
              "input_schema": {"type": "object", "properties": {
                  "query": {"type": "string"},
                  "offset": {"type": "integer", "description": "where to start in the results; default 0"}},
                  "required": ["query"]}}
RUN_TOOL = {"name": "run_tool", "description": "Run a tool from the catalogue by its name.",
            "input_schema": {"type": "object", "properties": {
                "name": {"type": "string"}, "arguments": {"type": "object"}}, "required": ["name", "arguments"]}}


def wire(tool: dict) -> dict:
    return {"type": "function", "function": {"name": tool["name"], "description": tool["description"],
                                             "parameters": tool["input_schema"]}}


TOOL_LIST = [wire(C.TOOLS[n]) for n in C.PRIMARY] + [wire(FIND_TOOLS), wire(RUN_TOOL)]

# ── search ───────────────────────────────────────────────────────────────

STOP = set("a an the to of for on in by with and or is it my our me i this that from at as be do can "
           "tool tools".split())


def tokens(text: str) -> list[str]:
    out = []
    for w in re.split(r"[^a-z0-9]+", text.lower()):
        if not w or w in STOP:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def _doc(t: dict) -> list[str]:
    words = [t["name"].replace("_", " ")] * 2 + [t["description"]]
    for k, v in t["input_schema"].get("properties", {}).items():
        words.append(k.replace("_", " "))
        words.extend(v.get("enum", []))
    return tokens(" ".join(words))


def trigrams(words: list[str]) -> set[str]:
    return {f" {w} "[i:i + 3] for w in words for i in range(len(w))}


DOCS = {n: _doc(t) for n, t in C.TOOLS.items()}
TRI = {n: trigrams(d) for n, d in DOCS.items()}
AVGDL = sum(len(d) for d in DOCS.values()) / len(DOCS)
DF = Counter(w for d in DOCS.values() for w in set(d))


def rank(query: str) -> list[tuple[str, float]]:
    """Every tool, best first: BM25 over words, plus the share of the query's letter trigrams the tool
    holds, so that, like an embedding search, every query has closest tools. An exact name comes first."""
    q = tokens(query)
    qt = trigrams(q)
    scores = {}
    for n, d in DOCS.items():
        tf = Counter(d)
        s = 0.0
        for w in q:
            if w in tf:
                idf = math.log(1 + (len(DOCS) - DF[w] + 0.5) / (DF[w] + 0.5))
                s += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(d) / AVGDL))
        scores[n] = s + (len(qt & TRI[n]) / len(qt) if qt else 0.0)
    exact = query.strip()
    if exact in scores:
        scores[exact] = 1e9
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


NAME_LIKE = re.compile(r"^[A-Za-z][A-Za-z0-9]*([_.][A-Za-z0-9]+)+$")


def find_tools(cond: str, query: str, offset: int = 0) -> dict:
    ranked = rank(query)
    offset = max(0, int(offset or 0))
    page = ranked[offset:offset + PAGE]
    entry = ((lambda n: {"name": n, "description": C.TOOLS[n]["description"]}) if cond == "names" else
             (lambda n: {"name": n, "description": C.TOOLS[n]["description"],
                         "input_schema": C.TOOLS[n]["input_schema"]}))
    out: dict = {"query": query, "results": [entry(n) for n, _ in page]}
    if cond == "plain":
        q = query.strip()
        if NAME_LIKE.match(q) and q not in C.TOOLS:
            out["named"] = f"No tool is named {q}."
        out["note"] = ("These are the closest tools; there is no further page. If none of them does what you "
                       "need, no tool here does it.")
    if cond == "paged" and offset + PAGE < len(ranked):
        out["more"] = f"Less close matches follow with the same query and offset={offset + PAGE}."
    return out


# ── tools ────────────────────────────────────────────────────────────────

def validate(value, schema: dict, path: str = "arguments") -> list[str]:
    t = schema.get("type")
    errs: list[str] = []
    if t == "object":
        if not isinstance(value, dict):
            return [f"{path} must be an object"]
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{path}: missing required field '{k}'")
        for k, v in value.items():
            if k not in props:
                if schema.get("additionalProperties") is False:
                    errs.append(f"{path}: unexpected field '{k}'")
            else:
                errs += validate(v, props[k], f"{path}.{k}")
        return errs
    if t == "array":
        if not isinstance(value, list):
            return [f"{path} must be an array"]
        for i, v in enumerate(value):
            errs += validate(v, schema["items"], f"{path}[{i}]")
        return errs
    ok = {"string": isinstance(value, str),
          "integer": isinstance(value, int) and not isinstance(value, bool)
          or isinstance(value, float) and value.is_integer(),
          "number": isinstance(value, (int, float)) and not isinstance(value, bool),
          "boolean": isinstance(value, bool)}.get(t, True)
    if not ok:
        return [f"{path}: {json.dumps(value)} is not of type '{t}'"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{path}: {json.dumps(value)} is not one of {json.dumps(schema['enum'])}"]
    return []


def execute(name: str, args, state: dict) -> dict:
    """Run a catalogue tool on the run's own synthetic records: a write stores what it was given, a read
    returns what was stored under the id it names, a list returns the stored records."""
    if isinstance(args, str):
        try:
            args = json.loads(args or "{}")
        except json.JSONDecodeError:
            return {"error": "arguments are not valid JSON"}
    if name not in C.TOOLS:
        return {"error": f"Unknown tool: {name}"}
    errs = validate(args if args is not None else {}, C.TOOLS[name]["input_schema"])
    if errs:
        return {"error": f"Invalid arguments for {name}: " + "; ".join(errs)}
    args = args or {}
    store = state.setdefault("store", {})
    ids = [v for k, v in args.items() if k.endswith("_id") and isinstance(v, str)]
    if C.TOOLS[name]["writes"]:
        target = next((i for i in ids if i in store), None)
        if target and not name.startswith(("create_", "add_", "log_", "schedule_", "request_")):
            store[target].update(args)
            return {"ok": True, "id": target, "record": store[target]}
        state["n"] = state.get("n", 0) + 1
        new = f"{name.split('_')[-1][:3].upper()}-{9000 + state['n']}"
        store[new] = {"id": new, "made_by": name, **args}
        return {"ok": True, "id": new}
    for i in ids:
        if i in store:
            return {"ok": True, "result": store[i]}
    key = next(iter(ids), None) or next((v for v in args.values() if isinstance(v, str)), None)
    if (name, key) in C.READS:
        return {"ok": True, "result": C.READS[(name, key)]}
    if name.startswith("list_"):
        return {"ok": True, "items": list(store.values())}
    return {"ok": True, "result": {"request": args, "note": "nothing further on record"}}


def dispatch(cond: str, name: str, raw: str, state: dict) -> tuple[dict, dict]:
    """One tool call -> (what the model is told, what the loop records)."""
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"error": "arguments are not valid JSON"}, {"tool": name, "target": name, "ok": False, "args": None}
    if not isinstance(args, dict):
        args = {}
    if name == "find_tools":
        res = find_tools(cond, str(args.get("query", "")), args.get("offset") or 0)
        return res, {"tool": "find_tools", "query": str(args.get("query", "")), "offset": args.get("offset") or 0,
                     "ok": True, "hits": [r["name"] for r in res["results"]]}
    if name == "run_tool":
        target, targs = str(args.get("name", "")), args.get("arguments", {})
    else:  # a primary tool, or a catalogue tool called by name without run_tool
        target, targs = name, args
    res = execute(target, targs, state)
    if isinstance(targs, str):
        try:
            targs = json.loads(targs)
        except json.JSONDecodeError:
            targs = None
    return res, {"tool": name, "target": target, "args": targs, "ok": "error" not in res}


# ── model calls ──────────────────────────────────────────────────────────

def req_hash(messages: list[dict]) -> str:
    return hashlib.sha256(json.dumps([SYSTEM, TOOL_LIST, messages], sort_keys=True).encode()).hexdigest()[:16]


class Cache:
    def __init__(self, label: str):
        self.path = RESULTS / f"{label}.jsonl"
        self.rows: dict[tuple, dict] = {}
        self.lock = threading.Lock()
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                r = json.loads(line)
                self.rows[(r["cond"], r["task"], r["rep"], r["step"])] = r

    def add(self, row: dict) -> None:
        with self.lock:
            self.rows[(row["cond"], row["task"], row["rep"], row["step"])] = row
            with self.path.open("a") as f:
                f.write(json.dumps(row, sort_keys=True) + "\n")


class Spend:
    def __init__(self, cap: float):
        self.cap, self.lock = cap, threading.Lock()
        self.spent = sum(json.loads(line)["usage"].get("cost") or 0
                         for p in RESULTS.glob("*.jsonl") for line in p.read_text().splitlines())

    def add(self, x: float) -> None:
        with self.lock:
            self.spent += x


def call(args, key: str, messages: list[dict]) -> dict | None:
    body = {"model": args.model, "messages": messages, "tools": TOOL_LIST, "tool_choice": "auto",
            "max_tokens": 8192, "usage": {"include": True},
            "provider": {"quantizations": ["fp8", "fp16", "bf16", "fp32", "unknown"], "require_parameters": True}}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json",
                                                         "Authorization": f"Bearer {key}"})
    for attempt in range(4):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                payload = json.loads(r.read())
            ch = (payload.get("choices") or [None])[0]
            if ch and ch.get("message") is not None and not ch.get("error"):
                m = ch["message"]
                return {"message": {"content": m.get("content"), "tool_calls": m.get("tool_calls")},
                        "finish": ch.get("finish_reason"), "provider": payload.get("provider"),
                        "usage": {k: (payload.get("usage") or {}).get(k)
                                  for k in ("prompt_tokens", "completion_tokens", "cost")},
                        "ms": round((time.perf_counter() - t0) * 1000)}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            print(f"  call failed ({exc}); retrying", file=sys.stderr)
        time.sleep(2 + 3 * attempt)
    return None


# ── the loop ─────────────────────────────────────────────────────────────

def run_one(cond: str, task: dict, rep: int, cache: Cache, net=None) -> dict:
    """Run (or replay) one task. `net` is (args, key, spend) to allow model calls; None replays only."""
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task["request"]}]
    calls, state, steps, final, status, mismatched = [], {}, [], None, "done", 0
    for step in range(MAX_STEPS):
        h = req_hash(messages[2:])
        row = cache.rows.get((cond, task["id"], rep, step))
        if row is not None and row["req"] != h:
            mismatched += 1
        if row is None:
            if net is None:
                status = "incomplete"
                break
            args, key, spend = net
            if spend.spent >= args.max_cost:
                status = "cap"
                break
            got = call(args, key, messages)
            if got is None:
                status = "failed"
                break
            row = {"cond": cond, "task": task["id"], "rep": rep, "step": step, "req": h, "model": args.model, **got}
            cache.add(row)
            spend.add(row["usage"].get("cost") or 0)
        steps.append(row)
        msg = row["message"]
        tcs = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         **({"tool_calls": tcs} if tcs else {})})
        if not tcs:
            final = msg.get("content") or ""
            break
        for tc in tcs:
            fn = tc.get("function") or {}
            res, rec = dispatch(cond, fn.get("name", ""), fn.get("arguments") or "{}", state)
            rec["step"] = step
            calls.append(rec)
            messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": json.dumps(res)})
    else:
        status = "cut_off"
    return {"cond": cond, "task": task["id"], "rep": rep, "status": status, "final": final, "calls": calls,
            "steps": steps, "mismatched": mismatched}


def run(args) -> int:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    RESULTS.mkdir(exist_ok=True)
    cache, spend = Cache(args.label), Spend(args.max_cost)
    conds = args.conditions.split(",") if args.conditions else CONDITIONS
    tasks = [t for t in C.TASKS if not args.tasks or t["id"] in args.tasks.split(",")]
    jobs = [(c, t, r) for r in range(args.reps) for c in conds for t in tasks]
    print(f"{args.label}: {len(jobs)} runs, ${spend.spent:.4f} spent so far (cap ${args.max_cost})")
    with ThreadPoolExecutor(args.workers) as ex:
        out = list(ex.map(lambda j: run_one(*j, cache, (args, key, spend)), jobs))
    print(f"{args.label}: {Counter(o['status'] for o in out)}; ${spend.spent:.4f} spent in all")
    return 0


# ── scoring ──────────────────────────────────────────────────────────────

def _norm(v):
    if isinstance(v, str):
        return v.strip().lower()
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return v


def matches(expected, actual) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(matches(v, actual.get(k)) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        left = list(actual)
        for e in expected:
            hit = next((a for a in left if matches(e, a)), None)
            if hit is None:
                return False
            left.remove(hit)
        return True
    if isinstance(expected, str) and re.match(r"^\d{4}-\d\d-\d\dT", expected):
        return isinstance(actual, str) and actual.startswith(expected)
    return _norm(expected) == _norm(actual)


def outcome(final: str | None) -> str:
    """CANNOT if the reply says CANNOT anywhere in capitals ("DONE is not appropriate here ... CANNOT:" is a
    CANNOT), else DONE if it starts with DONE, else unclear."""
    text = final or ""
    if re.search(r"\bCANNOT\b", text):
        return "CANNOT"
    return "DONE" if re.match(r"^\W*DONE\b", text, re.I) else "unclear"


def score(r: dict) -> dict:
    task = next(t for t in C.TASKS if t["id"] == r["task"])
    finds = [c for c in r["calls"] if c["tool"] == "find_tools"]
    keys = [(c["query"].strip().lower(), int(c["offset"] or 0)) for c in finds]
    runs = [c for c in r["calls"] if c["tool"] != "find_tools"]
    failed = [c for c in runs if not c["ok"]]
    fkeys = [(c["target"], json.dumps(c["args"], sort_keys=True)) for c in failed]
    writes = [c for c in runs if c["ok"] and c["target"] in C.TOOLS and C.TOOLS[c["target"]]["writes"]]
    out = outcome(r["final"])
    if task["kind"] == "exists":
        did = any(c["ok"] and c["target"] == task["tool"] and matches(task["args"], c["args"]) for c in runs)
        ok = did and out != "CANNOT" and r["status"] == "done"
        if ok and task.get("answer"):
            ok = task["answer"].lower() in (r["final"] or "").lower()
    else:
        stand = [c for c in writes if c["target"] in task["stand_ins"]]
        ok = out == "CANNOT" and not stand and r["status"] == "done"
    usage = [s["usage"] for s in r["steps"]]
    return {"kind": task["kind"], "success": ok, "outcome": out, "status": r["status"],
            "searches": len(finds), "repeated_searches": len(keys) - len(set(keys)),
            "paged_searches": sum(1 for _, o in keys if o > 0),
            "tool_calls": len(runs), "failed_calls": len(failed), "repeated_failed_calls": len(fkeys) - len(set(fkeys)),
            "unknown_tool_calls": sum(1 for c in runs if c["target"] not in C.TOOLS),
            "writes": len(writes), "stand_in_writes": sum(1 for c in writes if c["target"] in task.get("stand_ins", [])),
            "steps": len(r["steps"]),
            "prompt_tokens": sum(u.get("prompt_tokens") or 0 for u in usage),
            "completion_tokens": sum(u.get("completion_tokens") or 0 for u in usage),
            "cost": sum(u.get("cost") or 0 for u in usage)}


def _mean(xs):
    return round(sum(xs) / len(xs), 2) if xs else None


def summarize(label: str) -> dict:
    cache = Cache(label)
    reps = sorted({k[2] for k in cache.rows})
    out: dict = {"model": next(iter(cache.rows.values()))["model"] if cache.rows else None}
    per_task: dict = defaultdict(dict)
    mismatched = 0
    for cond in CONDITIONS:
        scored = []
        for t in C.TASKS:
            for rep in reps:
                if (cond, t["id"], rep, 0) not in cache.rows:
                    continue
                r = run_one(cond, t, rep, cache)
                if r["status"] in ("incomplete",):
                    continue
                mismatched += r["mismatched"]
                s = score(r) | {"task": t["id"], "rep": rep}
                scored.append(s)
                per_task[cond].setdefault(t["id"], []).append(
                    {k: s[k] for k in ("success", "outcome", "status", "searches", "repeated_searches",
                                       "failed_calls", "stand_in_writes")})
        if not scored:
            continue
        q: dict = {"runs": len(scored)}
        for kind in ("exists", "missing", "all"):
            ss = [s for s in scored if kind == "all" or s["kind"] == kind]
            if not ss:
                continue
            q[kind] = {"runs": len(ss), "success": sum(s["success"] for s in ss),
                       "success_rate": round(sum(s["success"] for s in ss) / len(ss), 3),
                       "searches_mean": _mean([s["searches"] for s in ss]),
                       "searches_max": max(s["searches"] for s in ss),
                       "repeated_searches_mean": _mean([s["repeated_searches"] for s in ss]),
                       "runs_with_repeated_search": sum(s["repeated_searches"] > 0 for s in ss),
                       "paged_searches_mean": _mean([s["paged_searches"] for s in ss]),
                       "failed_calls_mean": _mean([s["failed_calls"] for s in ss]),
                       "repeated_failed_calls_mean": _mean([s["repeated_failed_calls"] for s in ss]),
                       "unknown_tool_calls": sum(s["unknown_tool_calls"] for s in ss),
                       "stand_in_writes": sum(s["stand_in_writes"] for s in ss),
                       "cut_off": sum(s["status"] == "cut_off" for s in ss),
                       "outcomes": dict(Counter(s["outcome"] for s in ss)),
                       "steps_mean": _mean([s["steps"] for s in ss]),
                       "prompt_tokens_mean": round(sum(s["prompt_tokens"] for s in ss) / len(ss)),
                       "completion_tokens_mean": round(sum(s["completion_tokens"] for s in ss) / len(ss)),
                       "cost_per_run": round(sum(s["cost"] for s in ss) / len(ss), 5),
                       "cost": round(sum(s["cost"] for s in ss), 4)}
        out[cond] = q
    out["per_task"] = per_task
    out["requests_not_matching_cache"] = mismatched
    out["cached_calls"] = len(cache.rows)
    out["cost_usd"] = round(sum(r["usage"].get("cost") or 0 for r in cache.rows.values()), 4)
    return out


def report(_args) -> int:
    full = {p.stem: summarize(p.stem) for p in sorted(RESULTS.glob("*.jsonl"))}
    (RESULTS / "report.json").write_text(json.dumps(full, indent=1, sort_keys=True) + "\n")
    print("| model | result shape | tasks | success, tool exists | success, no tool | searches per task, "
          "exists / missing | repeated searches per task | cut off | prompt tokens per task | cost per task |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for label, r in full.items():
        for cond in CONDITIONS:
            q = r.get(cond)
            if not q:
                continue
            e, m, a = q.get("exists", {}), q.get("missing", {}), q["all"]
            print(f"| {label} | {cond} | {a['runs']} | {e.get('success')}/{e.get('runs')} | "
                  f"{m.get('success')}/{m.get('runs')} | {e.get('searches_mean')} / {m.get('searches_mean')} | "
                  f"{a['repeated_searches_mean']} | {a['cut_off']} | {a['prompt_tokens_mean']:,} | "
                  f"${a['cost_per_run']:.4f} |")
    total = sum(r["cost_usd"] for r in full.values())
    print(f"\n{sum(r['cached_calls'] for r in full.values())} cached model calls, ${total:.4f} in all; "
          f"requests not matching their cached hash: {sum(r['requests_not_matching_cache'] for r in full.values())}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--label", required=True)
    r.add_argument("--model", required=True)
    r.add_argument("--reps", type=int, default=3)
    r.add_argument("--conditions")
    r.add_argument("--tasks")
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--max-cost", type=float, default=3.0, help="stop when every cached call together costs this")
    r.set_defaults(fn=run)
    sub.add_parser("report").set_defaults(fn=report)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
