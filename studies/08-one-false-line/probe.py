#!/usr/bin/env python3
"""Does one false line in an agent's history stop it using a tool it has?

cases.py holds eleven conversations that end with the same request, "How many prospects are
currently in the pipeline?". The tool that answers it is offered in every one. Each conversation is
sent to a model as a chat completion with tools, and the model's first step is classified:

  called      it called list_pipeline
  other_tool  it called some other tool
  refused     it wrote text saying it cannot, with no tool call
  other_text  it wrote anything else with no tool call (a question, a guessed number)

Two more factors: the setup (`wide`, a production-sized prompt with 40 tools, or `small`, a short
prompt with six) and reasoning (`off`, `on`, or the model's `default`).

  OPENROUTER_API_KEY=... python3 probe.py run --model deepseek/deepseek-v4.1-flash --reasoning off
  python3 probe.py report

Every response is cached in results/<setup>__<reasoning>__<model>.jsonl, keyed by condition and trial; a failed call is
not cached and is retried on the next run. The spend cap counts every cached response in results/.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cases as C  # noqa: E402

RESULTS = HERE / "results"
URL = "https://openrouter.ai/api/v1/chat/completions"
CANNOT = re.compile(r"\b(can(?:no|')?t|cannot|unable|no tool|not able|(?:don't|do not|doesn't|does not) have|"
                    r"not one I have|"
                    r"(?:isn't|is not|not) available|unavailable|no way)\b", re.I)
OUTCOMES = ("called", "other_tool", "refused", "other_text")



def slug(model: str, setup: str) -> str:
    return setup.replace(" ", "__") + "__" + model.replace("/", "__")


def load(model: str, setup: str) -> dict[tuple, dict]:
    path = RESULTS / f"{slug(model, setup)}.jsonl"
    rows = {}
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            rows[(r["condition"], r["trial"])] = r
    return rows


def spent_total() -> float:
    total = 0.0
    for p in RESULTS.glob("*.jsonl"):
        total += sum(json.loads(line)["cost"] for line in p.read_text().splitlines())
    return total


def classify(tool_calls: list[dict], text: str) -> str:
    if tool_calls:
        return "called" if any(t["name"] == "list_pipeline" for t in tool_calls) else "other_tool"
    return "refused" if CANNOT.search(text or "") else "other_text"


def ask(args, key: str, condition: str, trial: int) -> dict:
    body = {"model": args.model, "messages": C.messages(condition, args.setup.split()[0]),
            "tools": C.tools(args.setup.split()[0]),
            "tool_choice": "auto", "max_tokens": args.max_tokens, "usage": {"include": True}}
    if args.reasoning != "default":
        body["reasoning"] = {"enabled": args.reasoning == "on"}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    status, payload, t0 = 0, {}, time.perf_counter()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                status, payload = r.status, json.loads(r.read())
        except urllib.error.HTTPError as exc:
            status, payload = exc.code, {}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            status, payload = 0, {}
        if status == 200 and payload.get("choices"):
            break
        time.sleep(2 + 2 * attempt)
    choice = (payload.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    calls = [{"name": (t.get("function") or {}).get("name"), "arguments": (t.get("function") or {}).get("arguments")}
             for t in msg.get("tool_calls") or []]
    text = msg.get("content") or ""
    usage = payload.get("usage") or {}
    ok = status == 200 and bool(payload.get("choices")) and (bool(calls) or bool(text.strip()))
    return {"model": args.model, "setup": args.setup, "condition": condition, "trial": trial, "ok": ok, "status": status,
            "outcome": classify(calls, text) if ok else None, "tool_calls": calls, "text": text,
            "reasoning": (msg.get("reasoning") or "")[:3000], "finish": choice.get("finish_reason"),
            "provider": payload.get("provider"), "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"), "cost": float(usage.get("cost") or 0),
            "ms": round((time.perf_counter() - t0) * 1000)}


def run(args) -> int:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    RESULTS.mkdir(exist_ok=True)
    args.setup = f"{args.setup} {args.reasoning}"
    seen = load(args.model, args.setup)
    conds = args.conditions.split(",") if args.conditions else list(C.CONDITIONS)
    todo = [(c, t) for c in conds for t in range(1, args.trials + 1) if (c, t) not in seen]
    spent = spent_total()
    if spent >= args.max_cost:
        raise SystemExit(f"spend cap reached (${spent:.4f})")
    failed = 0
    with ThreadPoolExecutor(args.workers) as ex, (RESULTS / f"{slug(args.model, args.setup)}.jsonl").open("a") as f:
        for row in ex.map(lambda ct: ask(args, key, *ct), todo):
            if not row["ok"]:
                failed += 1
                continue
            f.write(json.dumps(row, sort_keys=True) + "\n")
            f.flush()
            spent += row["cost"]
            if spent >= args.max_cost:
                raise SystemExit(f"spend cap reached (${spent:.4f})")
    print(f"{args.setup} {args.model}: {len(load(args.model, args.setup))} responses, {failed} failed (not cached), "
          f"all results ${spent:.4f}")
    return 0


def summarize(model: str, setup: str) -> dict:
    rows = load(model, setup)
    out = {}
    for cond in C.CONDITIONS:
        rs = [r for (c, _), r in rows.items() if c == cond]
        if not rs:
            continue
        # Classified again from the cached reply, so the rule can change without new calls.
        n = Counter(classify(r["tool_calls"], r["text"]) for r in rs)
        out[cond] = {"trials": len(rs), **{k: n[k] for k in OUTCOMES},
                     "called_share": round(n["called"] / len(rs), 3)}
    if rows:
        vals = list(rows.values())
        out["calls"] = {"responses": len(vals), "cost_usd": round(sum(r["cost"] for r in vals), 4),
                        "input_tokens_mean": round(sum(r["input_tokens"] or 0 for r in vals) / len(vals)),
                        "output_tokens_mean": round(sum(r["output_tokens"] or 0 for r in vals) / len(vals))}
    return out


def report(_args) -> int:
    full = {}
    for p in sorted(RESULTS.glob("*.jsonl")):
        first = json.loads(p.read_text().splitlines()[0])
        full[f"{first['setup']} {first['model']}"] = summarize(first["model"], first["setup"])
    (RESULTS / "report.json").write_text(json.dumps(full, indent=1, sort_keys=True) + "\n")
    models = list(full)
    models.sort(key=lambda m: (m.split(" ")[0], m.split(" ")[1] != "off", m))
    print("| condition | " + " | ".join(" ".join(m.split(" ")[:2]) + " " + m.split("/")[-1] for m in models) + " |")
    print("|---|" + "---|" * len(models))
    for cond in C.CONDITIONS:
        cells = []
        for m in models:
            q = full[m].get(cond)
            cells.append(f"{q['called']}/{q['trials']}" if q else "")
        print(f"| {cond} | " + " | ".join(cells) + " |")
    print()
    for m in models:
        c = full[m].get("calls", {})
        print(f"{m}: {c.get('responses')} responses, ${c.get('cost_usd')}, "
              f"mean in {c.get('input_tokens_mean')} / out {c.get('output_tokens_mean')} tokens")
    print(f"total ${sum(full[m].get('calls', {}).get('cost_usd', 0) for m in models):.4f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--model", required=True)
    r.add_argument("--setup", choices=("small", "wide"), default="wide")
    r.add_argument("--reasoning", choices=("on", "off", "default"), default="on")
    r.add_argument("--trials", type=int, default=15)
    r.add_argument("--conditions", help="comma-separated subset; default all")
    r.add_argument("--max-tokens", type=int, default=4000)
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--max-cost", type=float, default=3.0, help="cap on all cached responses together")
    r.set_defaults(fn=run)
    sub.add_parser("report").set_defaults(fn=report)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
