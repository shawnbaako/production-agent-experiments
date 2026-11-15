#!/usr/bin/env python3
"""Check each sentence of an agent's output against its sources, with two different evidence sets.

cases.py holds 48 synthetic outputs, each with the records it cites, the other records the agent read,
and a label for every sentence. Each scorer is asked, one sentence at a time, whether the sentence is
supported by the records it is shown. Conditions:

  cited          only the records the output cites or replies to
  all            the cited records and everything else the agent read
  all_reworded   as `all`, with the question in different words

A sentence is flagged when P(supported) falls below a threshold fitted on the development split.
The report asks two things: are the planted errors still caught when the checker sees more, and how
many correct sentences does it flag in each condition?

  OPENROUTER_API_KEY=... python3 check.py run --scorer jev-1.14 --model typesafe/jev-1.14
  python3 check.py run --scorer laya-typed-decisions --model typed-decisions \
      --url http://127.0.0.1:8091/v1/systemone --key-env "" --workers 1
  python3 check.py report

Every answer is cached in results/<scorer>.jsonl. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
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
QUESTION = "Is this sentence stated in, or supported by, the records above?"
REWORDED = "Do the records above back up what this sentence says?"
CONDITIONS = ("cited", "all", "all_reworded")
ERRORS = {"unsupported", "contradicted"}


def split_of(case: dict) -> str:
    return "dev" if int(case["id"][1:]) % 2 == 0 else "held"


def records_text(records: list[dict]) -> str:
    return "\n\n".join(f"[{r['id']} · {r['kind']}]\n{r['text'].strip()}" for r in records)


def state(case: dict, condition: str, sentence: str) -> str:
    recs = case["cited"] if condition == "cited" else case["cited"] + case["other"]
    return f"Records:\n\n{records_text(recs)}\n\nSentence:\n{sentence}"


def items() -> list[dict]:
    out = []
    for case in C.CASES:
        for i, s in enumerate(case["output"]):
            out.append({"case": case["id"], "n": i, "case_obj": case, "text": s["text"], "label": s["label"],
                        "error": s.get("error"), "split": split_of(case)})
    return out


def load(scorer: str) -> dict[tuple, dict]:
    path = RESULTS / f"{scorer}.jsonl"
    rows = {}
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            rows[(r["condition"], r["case"], r["n"])] = r
    return rows


def ask(args, key: str | None, condition: str, it: dict) -> dict:
    q = REWORDED if condition == "all_reworded" else QUESTION
    body = {"model": args.model, "state": state(it["case_obj"], condition, it["text"]),
            "questions": {"q": {"type": "noul", "instructions": q}}, **json.loads(args.extra_body or "{}")}
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(args.url, data=json.dumps(body).encode(), method="POST", headers=headers)
    status, payload, t0 = 0, {}, time.perf_counter()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                status, payload = r.status, json.loads(r.read())
        except urllib.error.HTTPError as exc:
            status, payload = exc.code, {}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            status, payload = 0, {}
        if status == 200:
            break
        time.sleep(1 + attempt)
    ans = ((payload.get("answers") or {}) if isinstance(payload, dict) else {}).get("q") or {}
    p = float(ans["noul"]) if isinstance(ans.get("noul"), (int, float)) else None
    usage = (payload.get("usage") or {}) if isinstance(payload, dict) else {}
    return {"condition": condition, "case": it["case"], "n": it["n"], "p": p, "status": status,
            "ms": round((time.perf_counter() - t0) * 1000), "tokens": usage.get("input_tokens"),
            "cost": float(usage.get("cost") or 0)}


def run(args) -> int:
    key = os.environ.get(args.key_env, "").strip() if args.key_env else None
    if args.key_env and not key:
        raise SystemExit(f"{args.key_env} is not set")
    RESULTS.mkdir(exist_ok=True)
    seen = load(args.scorer)
    todo = [(c, it) for c in CONDITIONS for it in items() if (c, it["case"], it["n"]) not in seen]
    spent = sum(r["cost"] for r in seen.values())
    with ThreadPoolExecutor(args.workers) as ex, (RESULTS / f"{args.scorer}.jsonl").open("a") as f:
        for row in ex.map(lambda t: ask(args, key, *t), todo):
            if row["status"] == 200 and row["p"] is not None:
                f.write(json.dumps(row, sort_keys=True) + "\n")
                spent += row["cost"]
            if spent >= args.max_cost:
                raise SystemExit(f"spend cap reached (${spent:.4f})")
    print(f"{args.scorer}: {len(load(args.scorer))} answers, ${spent:.4f}")
    return 0


# ── metrics ──────────────────────────────────────────────────────────────

def auroc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def fit_threshold(rows: list[tuple[float, bool]]) -> float:
    """Best-F1 threshold for flagging errors (flag when P(supported) < t)."""
    best, best_f1 = 0.5, -1.0
    for t in sorted({p for p, _ in rows} | {1.01}):
        tp = sum(p < t and e for p, e in rows)
        fp = sum(p < t and not e for p, e in rows)
        fn = sum(p >= t and e for p, e in rows)
        f1 = 2 * tp / max(1, 2 * tp + fp + fn)
        if f1 > best_f1:
            best, best_f1 = t, f1
    return best


def summarize(scorer: str) -> dict:
    rows = load(scorer)
    its = items()
    out: dict = {}
    for cond in CONDITIONS:
        def scored(split):
            return [(it, rows[(cond, it["case"], it["n"])]["p"]) for it in its
                    if it["split"] == split and (cond, it["case"], it["n"]) in rows]
        dev, held = scored("dev"), scored("held")
        if not held:
            continue
        # Thresholds are fitted on sentences that make a claim; the reworded condition reuses `all`'s.
        fit_on = "all" if cond == "all_reworded" else cond
        dev_fit = [(rows[(fit_on, it["case"], it["n"])]["p"], it["label"] in ERRORS) for it in its
                   if it["split"] == "dev" and it["label"] != "not_a_claim" and (fit_on, it["case"], it["n"]) in rows]
        t = fit_threshold(dev_fit) if dev_fit else 0.5
        flagged = Counter(it["label"] for it, p in held if p < t)
        total = Counter(it["label"] for it, _ in held)
        outputs = len({it["case"] for it, _ in held})
        err_by_type = Counter(it["error"] for it, p in held if it["label"] in ERRORS and p < t)
        err_total = Counter(it["error"] for it, _ in held if it["label"] in ERRORS)
        out[cond] = {
            "threshold": round(t, 4),
            "held_outputs": outputs,
            "held_sentences": len(held),
            "errors_caught": sum(flagged[k] for k in ERRORS), "errors": sum(total[k] for k in ERRORS),
            "flagged_by_label": dict(flagged), "sentences_by_label": dict(total),
            "false_flags_per_output": round(sum(flagged[k] for k in ("cited", "other")) / outputs, 2),
            "other_flagged_share": round(flagged["other"] / max(1, total["other"]), 3),
            "cited_flagged_share": round(flagged["cited"] / max(1, total["cited"]), 3),
            "precision": round(sum(flagged[k] for k in ERRORS) / max(1, sum(flagged.values())), 3),
            "auroc_errors_vs_true": round(auroc([-p for it, p in held if it["label"] in ERRORS],
                                                [-p for it, p in held if it["label"] in ("cited", "other")]), 3),
            "auroc_errors_vs_other": round(auroc([-p for it, p in held if it["label"] in ERRORS],
                                                 [-p for it, p in held if it["label"] == "other"]), 3),
            "errors_caught_by_type": {k: f"{err_by_type[k]}/{v}" for k, v in sorted(err_total.items())},
        }
    calls = [r for r in rows.values()]
    if calls:
        ms = sorted(r["ms"] for r in calls)
        out["calls"] = {"answers": len(calls), "latency_ms_p50": ms[len(ms) // 2],
                        "input_tokens_mean": round(sum(r.get("tokens") or 0 for r in calls) / len(calls)),
                        "cost_usd": round(sum(r["cost"] for r in calls), 4)}
    return out


def report(_args) -> int:
    full = {p.stem: summarize(p.stem) for p in sorted(RESULTS.glob("*.jsonl"))}
    (RESULTS / "report.json").write_text(json.dumps(full, indent=1, sort_keys=True) + "\n")
    print("| scorer | condition | errors caught | true sentences flagged per output | of `other` flagged | "
          "of `cited` flagged | precision | AUROC errors vs true |")
    print("|---|---|---|---|---|---|---|---|")
    for s, r in full.items():
        for cond in CONDITIONS:
            q = r.get(cond)
            if q:
                print(f"| {s} | {cond} | {q['errors_caught']}/{q['errors']} | {q['false_flags_per_output']} | "
                      f"{q['other_flagged_share']:.0%} | {q['cited_flagged_share']:.0%} | {q['precision']:.2f} | "
                      f"{q['auroc_errors_vs_true']:.3f} |")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--scorer", required=True)
    r.add_argument("--model", required=True)
    r.add_argument("--url", default="https://openrouter.ai/api/v1/systemone")
    r.add_argument("--key-env", default="OPENROUTER_API_KEY", help='use "" for an endpoint without a key')
    r.add_argument("--extra-body")
    r.add_argument("--workers", type=int, default=12)
    r.add_argument("--max-cost", type=float, default=1.0)
    r.set_defaults(fn=run)
    sub.add_parser("report").set_defaults(fn=report)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
