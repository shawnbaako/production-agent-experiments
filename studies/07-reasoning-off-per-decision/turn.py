#!/usr/bin/env python3
"""Turn reasoning off for one decision, or for the rest of the turn, after a decision runs out of room.

A minimal tool-calling agent loop runs each task in cases.py: one request, a small world behind
seventeen tools, and one write that is refused every time it is sent unchanged. Arms:

  on               reasoning on for every decision; no decision is squeezed
  off              reasoning off for every decision; no decision is squeezed
  decision_off     the turn's second decision is sent with 8 tokens of room, so reasoning uses it up and
                   nothing is answered; that decision is asked again with reasoning off and the normal room,
                   and the next decision has reasoning on again
  turn_off         the same squeeze and retry, and reasoning stays off for the rest of the turn
  decision_bigger  the same squeeze; that decision is asked again with reasoning on and the normal room

The squeeze stands in for a decision whose reasoning does not converge in production: it is a real
reply that reasoned through all its room and answered nothing. A decision that runs out of room
without a squeeze is handled by the arm's own rule.

  OPENROUTER_API_KEY=... python3 turn.py run --model deepseek/deepseek-v4.1-flash
  python3 turn.py report

Every model response is cached in results/calls/<model>.jsonl, keyed by the exact request and the
repetition index, so `report` replays every turn from the cache without a call. Failed calls are not
cached. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cases as C  # noqa: E402

RESULTS = HERE / "results"
CALLS = RESULTS / "calls"
URL = "https://openrouter.ai/api/v1/chat/completions"
ARMS = ("on", "off", "decision_off", "turn_off", "decision_bigger")
ROOM = 8192          # normal output room per decision
SQUEEZE = 8          # room for the squeezed decision
SQUEEZED_DECISION = 2
MAX_DECISIONS = 14   # decisions per turn, including retries
JUDGE_MODEL = "deepseek/deepseek-v4.1-flash"
PRECISIONS = ["fp8", "fp16", "bf16", "fp32", "unknown"]
IGNORE = {"deepseek/deepseek-v4.1-flash": ["baseten", "decart"]}


def slug(model: str) -> str:
    return model.split("/")[-1]


class Cache:
    """Responses by request key; appends new ones. `offline` raises on a miss instead of calling."""

    def __init__(self, model: str, key: str | None, max_cost: float, spent_elsewhere: float):
        self.model, self.key, self.max_cost = model, key, max_cost
        self.path = CALLS / f"{slug(model)}.jsonl"
        self.rows: dict[str, dict] = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                r = json.loads(line)
                self.rows[r["key"]] = r
        self.spent = spent_elsewhere + sum(r["cost"] for r in self.rows.values())
        self.lock = threading.Lock()
        self.pending: dict[str, threading.Event] = {}

    def get(self, body: dict, rep) -> dict:
        k = hashlib.sha256(json.dumps({"body": body, "rep": rep}, sort_keys=True).encode()).hexdigest()[:24]
        with self.lock:
            if k in self.rows:
                return self.rows[k]
            ev = self.pending.get(k)
            if ev is None:
                self.pending[k] = threading.Event()
        if ev is not None:  # another thread is fetching the same request
            ev.wait()
            return self.get(body, rep)
        try:
            if not self.key:
                raise SystemExit(f"cache miss with no key ({self.model}); run `run` first")
            if self.spent >= self.max_cost:
                raise SystemExit(f"spend cap reached (${self.spent:.4f})")
            row = fetch(body, self.key)
            row["key"] = k
            if row.get("ok"):
                with self.lock:
                    self.rows[k] = row
                    self.spent += row["cost"]
                    with self.path.open("a") as f:
                        f.write(json.dumps(row, sort_keys=True) + "\n")
                return row
            raise RuntimeError(f"call failed: {row.get('error')}")
        finally:
            with self.lock:
                self.pending.pop(k).set()


def fetch(body: dict, key: str) -> dict:
    data = json.dumps(body).encode()
    err = ""
    for attempt in range(4):
        req = urllib.request.Request(URL, data=data, method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read())
        except urllib.error.HTTPError as exc:
            err = f"HTTP {exc.code} {exc.read()[:200]!r}"
            time.sleep(2 + 3 * attempt)
            continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            err = repr(exc)
            time.sleep(2 + 3 * attempt)
            continue
        if not d.get("choices"):
            err = f"no choices: {str(d)[:200]}"
            time.sleep(2 + 3 * attempt)
            continue
        c = d["choices"][0]
        m = c.get("message") or {}
        u = d.get("usage") or {}
        return {"ok": True, "finish": c.get("finish_reason"), "content": m.get("content") or "",
                "tool_calls": [{"name": t["function"]["name"], "arguments": t["function"].get("arguments") or ""}
                               for t in (m.get("tool_calls") or [])],
                "reasoning_chars": len(m.get("reasoning") or ""),
                "prompt_tokens": u.get("prompt_tokens") or 0, "completion_tokens": u.get("completion_tokens") or 0,
                "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0,
                "cost": float(u.get("cost") or 0), "provider": d.get("provider"),
                "ms": round((time.perf_counter() - t0) * 1000)}
    return {"ok": False, "error": err}


def request(model: str, messages: list, reasoning: bool, room: int, tools: bool = True) -> dict:
    provider = {"zdr": True, "sort": "throughput", "quantizations": PRECISIONS, "require_parameters": True}
    if model in IGNORE:
        provider["ignore"] = IGNORE[model]
    body = {"model": model, "messages": messages, "max_tokens": room,
            "reasoning": {"enabled": reasoning}, "provider": provider, "usage": {"include": True}}
    if tools:
        body["tools"] = C.TOOLS
    return body


def no_answer(r: dict) -> bool:
    """Production's no-answer case: cut at its room, or neither an answer nor a tool call."""
    return r["finish"] == "length" or (not r["content"].strip() and not r["tool_calls"])


def parse_args(raw: str):
    try:
        v = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return None
    return v


def canon(name: str, raw: str) -> str:
    v = parse_args(raw)
    return name + " " + (json.dumps(v, sort_keys=True) if v is not None else raw)


def failed(result: dict) -> bool:
    return result.get("status") == "refused" or result.get("results") == []


def run_turn(cache: Cache, task: dict, arm: str, rep: int) -> dict:
    """One turn of the loop. Returns its trace and metrics."""
    model = cache.model
    world = C.new_world(task)
    messages = [{"role": "system", "content": C.SYSTEM}, *C.HISTORY, {"role": "user", "content": task["request"]}]
    think = arm != "off"
    decision, calls_made, steps, trace = 0, 0, 0, []
    squeezed = exhausted_squeeze = False
    reply = None
    seen_failed: dict[str, int] = {}
    repeats = 0
    first_off_step = None
    while steps < MAX_DECISIONS:
        decision += 1
        room, this_think = ROOM, think
        squeeze_now = arm in ("decision_off", "turn_off", "decision_bigger") and decision == SQUEEZED_DECISION
        if squeeze_now:
            room, this_think, squeezed = SQUEEZE, True, True
        sent = [request(model, messages, this_think, room)]
        r = cache.get(sent[0], rep)
        steps += 1
        trace.append({"decision": decision, "reasoning": this_think, "room": room, "finish": r["finish"],
                      "calls": [t["name"] for t in r["tool_calls"]], "tokens": r["completion_tokens"]})
        retries = 0
        while no_answer(r) and steps < MAX_DECISIONS and retries < 3:
            retries += 1
            if squeeze_now and retries == 1:
                exhausted_squeeze = True
            # The arm's rule for a decision that ran out of room.
            if arm in ("decision_off", "turn_off"):
                this_think = False
                if arm == "turn_off":
                    think = False
                    first_off_step = first_off_step or decision
            room = ROOM if (squeeze_now and retries == 1) else min(room * 2, 32768) if arm == "decision_bigger" \
                else ROOM
            body = request(model, messages, this_think, room)
            # An identical retry is a new sample: its cache key carries how many times it was sent before.
            again = sum(b == body for b in sent)
            sent.append(body)
            r = cache.get(body, rep if not again else f"{rep}.{again}")
            steps += 1
            trace.append({"decision": decision, "retry": retries, "reasoning": this_think, "room": room,
                          "finish": r["finish"], "calls": [t["name"] for t in r["tool_calls"]],
                          "tokens": r["completion_tokens"]})
        if no_answer(r):
            break
        if not r["tool_calls"]:
            reply = r["content"]
            break
        msg = {"role": "assistant", "content": r["content"] or None, "tool_calls": []}
        results = []
        for i, t in enumerate(r["tool_calls"]):
            cid = f"call_{decision}_{i}"
            msg["tool_calls"].append({"id": cid, "type": "function",
                                      "function": {"name": t["name"], "arguments": t["arguments"]}})
            args = parse_args(t["arguments"])
            res = C.execute(task, world, t["name"], args) if args is not None else \
                {"status": "refused", "error": "arguments are not valid JSON"}
            key = canon(t["name"], t["arguments"])
            if key in seen_failed:
                repeats += 1
            if failed(res):
                seen_failed[key] = seen_failed.get(key, 0) + 1
            calls_made += 1
            trace[-1].setdefault("results", []).append(res.get("status") + ("" if not failed(res) else " (failed)"))
            results.append({"role": "tool", "tool_call_id": cid, "content": json.dumps(res)})
        messages.append(msg)
        messages.extend(results)
    return {"task": task["id"], "arm": arm, "rep": rep, "model": model, "trace": trace, "reply": reply,
            "decisions": decision, "model_calls": steps, "tool_calls": calls_made,
            "repeats_of_failed": repeats, "max_same_failed": max(seen_failed.values(), default=0),
            "refused": bool(seen_failed), "squeezed": squeezed, "squeeze_exhausted": exhausted_squeeze,
            "success": bool(reply is not None and task["success"](world, reply or "")),
            "finished": reply is not None, "world_effects": world["effects"]}


def turn_cost(cache: Cache, task: dict, arm: str, rep: int) -> tuple[int, int, float]:
    """Tokens and cost of a turn, recomputed from the requests it made."""
    tot = [0, 0, 0.0]
    orig = cache.get

    def counting(body, rep_):
        r = orig(body, rep_)
        tot[0] += r["prompt_tokens"]
        tot[1] += r["completion_tokens"]
        tot[2] += r["cost"]
        return r
    cache.get = counting
    try:
        run_turn(cache, task, arm, rep)
    finally:
        cache.get = orig
    return tot[0], tot[1], tot[2]


def judge(cache: Cache, task: dict, reply: str, rep: int) -> bool | None:
    if not task.get("claim") or not reply:
        return None
    prompt = (f"A person asked an assistant: {task['request']}\n\nThe assistant replied:\n{reply}\n\n"
              f"Question: {task['claim']}\nAnswer with one word, yes or no.")
    body = request(JUDGE_MODEL, [{"role": "user", "content": prompt}], True, 2048, tools=False)
    r = cache.get(body, 0)
    return r["content"].strip().lower().startswith("yes")


def all_spent() -> float:
    total = 0.0
    for p in CALLS.glob("*.jsonl"):
        total += sum(json.loads(line)["cost"] for line in p.read_text().splitlines())
    return total


def run(args) -> int:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    CALLS.mkdir(parents=True, exist_ok=True)
    elsewhere = all_spent()
    cache = Cache(args.model, key, args.max_cost, elsewhere - _file_cost(args.model))
    judge_cache = cache if args.model == JUDGE_MODEL else Cache(JUDGE_MODEL, key, args.max_cost,
                                                                elsewhere - _file_cost(JUDGE_MODEL))
    tasks = [t for t in C.TASKS if not args.tasks or t["id"] in args.tasks.split(",")]
    arms = args.arms.split(",") if args.arms else ARMS
    jobs = [(t, a, rep) for rep in range(args.reps) for t in tasks for a in arms]

    def one(job):
        t, a, rep = job
        try:
            out = run_turn(cache, t, a, rep)
            if out["reply"] and _claim_applies(t, out):
                judge(judge_cache, t, out["reply"], rep)
            return f"{t['id']} {a} {rep}: success={out['success']} repeats={out['repeats_of_failed']}"
        except RuntimeError as exc:
            return f"{t['id']} {a} {rep}: {exc}"
    with ThreadPoolExecutor(args.workers) as ex:
        for line in ex.map(one, jobs):
            print(line, flush=True)
    print(f"{args.model}: spent ${all_spent():.4f} in all")
    return 0


def _file_cost(model: str) -> float:
    p = CALLS / f"{slug(model)}.jsonl"
    return sum(json.loads(line)["cost"] for line in p.read_text().splitlines()) if p.exists() else 0.0


def _claim_applies(task: dict, out: dict) -> bool:
    """The refused action never went through, so a reply saying it did is false."""
    return bool(task.get("claim")) and out["refused"] and not any(
        e["tool"] == task["refused_tool"] for e in out["world_effects"])


# ── report ───────────────────────────────────────────────────────────────

def report(args) -> int:
    out: dict = {"arms": list(ARMS), "models": {}}
    judge_cache = Cache(JUDGE_MODEL, None, 0, 0)
    traces = []
    models = args.models.split(",") if args.models else DEFAULT_MODELS
    for model in models:
        cache = Cache(model, None, 0, 0)
        if not cache.rows:
            continue
        per_arm = {}
        for arm in ARMS:
            runs = []
            for rep in range(args.reps):
                for t in C.TASKS:
                    try:
                        o = run_turn(cache, t, arm, rep)
                    except SystemExit:
                        continue
                    o["prompt_tokens"], o["completion_tokens"], o["cost"] = turn_cost(cache, t, arm, rep)
                    o["false_claim"] = judge(judge_cache, t, o["reply"], rep) if _claim_applies(t, o) else None
                    runs.append(o)
                    traces.append({k: v for k, v in o.items() if k != "world_effects"})
            if not runs:
                continue
            n = len(runs)
            ref = [o for o in runs if o["refused"]]
            claims = [o for o in runs if o["false_claim"] is not None]
            per_arm[arm] = {
                "turns": n,
                "done": sum(o["success"] for o in runs),
                "handed_back": sum(o["finished"] and not o["success"] and not o["false_claim"] for o in runs),
                "turns_with_a_failed_call": len(ref),
                "repeats_of_failed_calls": sum(o["repeats_of_failed"] for o in runs),
                "turns_with_a_repeat": sum(o["repeats_of_failed"] > 0 for o in runs),
                "turns_sending_one_failed_call_3_times_or_more": sum(o["max_same_failed"] >= 3 for o in runs),
                "unfinished": sum(not o["finished"] for o in runs),
                "squeeze_exhausted": sum(o["squeeze_exhausted"] for o in runs),
                "false_claims": sum(bool(o["false_claim"]) for o in claims), "claims_judged": len(claims),
                "model_calls_mean": round(sum(o["model_calls"] for o in runs) / n, 2),
                "completion_tokens_mean": round(sum(o["completion_tokens"] for o in runs) / n),
                "prompt_tokens_mean": round(sum(o["prompt_tokens"] for o in runs) / n),
                "cost_per_turn": round(sum(o["cost"] for o in runs) / n, 6),
            }
        out["models"][model] = per_arm
    out["spent_usd"] = round(all_spent(), 4)
    (RESULTS / "report.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    with (RESULTS / "turns.jsonl").open("w") as f:
        for t in traces:
            f.write(json.dumps(t, sort_keys=True) + "\n")
    print("| model | arm | done | handed back | repeated failed calls | turns with a repeat | one call sent 3+ times | "
          "unfinished | false claims | model calls / turn | output tokens / turn | cost / turn |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for model, per in out["models"].items():
        for arm, s in per.items():
            print(f"| {slug(model)} | {arm} | {s['done']}/{s['turns']} | {s['handed_back']} | {s['repeats_of_failed_calls']} | "
                  f"{s['turns_with_a_repeat']} | {s['turns_sending_one_failed_call_3_times_or_more']} | "
                  f"{s['unfinished']} | {s['false_claims']}/{s['claims_judged']} | {s['model_calls_mean']} | "
                  f"{s['completion_tokens_mean']} | ${s['cost_per_turn']:.5f} |")
    print(f"\nspent: ${out['spent_usd']}")
    return 0


DEFAULT_MODELS = ["deepseek/deepseek-v4.1-flash", "deepseek/deepseek-v4-flash-0731", "qwen/qwen3.6-35b-a3b"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--model", required=True)
    r.add_argument("--reps", type=int, default=5)
    r.add_argument("--tasks")
    r.add_argument("--arms")
    r.add_argument("--workers", type=int, default=12)
    r.add_argument("--max-cost", type=float, default=3.0, help="cap on all spend in results/calls")
    r.set_defaults(fn=run)
    rp = sub.add_parser("report")
    rp.add_argument("--reps", type=int, default=5)
    rp.add_argument("--models")
    rp.set_defaults(fn=report)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
