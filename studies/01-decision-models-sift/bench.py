#!/usr/bin/env python3
"""Rank a large set with one yes-no question per item, and compare scorers on the same items.

The corpus is synthetic (corpus.py). Each scorer gives every item a score for a question;
the report says how well the planted positives rise to the top. Scorers:

  systemone  a decision model behind the Jev-style `/v1/systemone` protocol
             (TypeSafe Jev through OpenRouter, a local Laya server, Clef)
  logprob    a chat model on an OpenAI-compatible endpoint, read through the
             probability of "yes" against "no" on its first answer token
  embed      an embedding model on an OpenAI-compatible endpoint (cosine to the question)
  bm25       BM25 of the question against the item
  keyword    substring match on hand-picked terms (what a plain mailbox search does)

Every answer is cached in results/answers/<scorer>.jsonl, so a rerun spends nothing
and anyone can recompute the report from the committed answers.

Examples:
  python3 bench.py run --scorer bm25 --kind bm25
  python3 bench.py run --scorer keyword --kind keyword
  python3 bench.py run --scorer laya-typed-decisions --kind systemone \
      --url http://127.0.0.1:8091/v1/systemone --model typed-decisions --workers 1
  OPENROUTER_API_KEY=... python3 bench.py run --scorer jev-1.14 --kind systemone \
      --url https://openrouter.ai/api/v1/systemone --model typesafe/jev-1.14 \
      --key-env OPENROUTER_API_KEY --workers 16
  python3 bench.py run --scorer qwen-logprob --kind logprob \
      --url http://127.0.0.1:8080/v1/chat/completions --model qwen3.8-27b --key-env LLM_KEY
  python3 bench.py report

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus  # noqa: E402

ANSWERS = HERE / "results" / "answers"
REPORT = HERE / "results" / "report.json"
PHASES = ("dev", "held", "reword")


# ── the questions ────────────────────────────────────────────────────────

def questions() -> list[dict]:
    """Every question under test: its items, wording, rewording and how an item becomes state."""
    mail, promises, accounts = corpus.mail_set(), corpus.promise_set(), corpus.account_set()
    out = []
    for key, wording in corpus.MAIL_QUESTIONS.items():
        out.append({"key": key, "items": mail, "q": wording, "reworded": corpus.MAIL_REWORDED[key],
                    "state": lambda it: it.text, "query": wording,
                    "positive": lambda it, k=key: k in it.labels,
                    "keywords": corpus.MAIL_KEYWORDS[key]})
    for email, (client, body) in corpus.NEW_EMAILS.items():
        out.append({"key": f"promise_{email}", "items": promises, "q": corpus.PROMISE_QUESTION,
                    "reworded": corpus.PROMISE_REWORDED,
                    "state": lambda it, b=body: f"New email:\n{b}\n\nPromise:\n{it.text}",
                    "query": body,  # for retrieval baselines the new email is the query
                    "positive": lambda it, e=email: e in it.labels,
                    "keywords": [client]})
    out.append({"key": "clinical_lab", "items": accounts, "q": corpus.ACCOUNT_QUESTION,
                "reworded": corpus.ACCOUNT_REWORDED, "state": lambda it: it.text,
                "query": corpus.ACCOUNT_QUESTION,
                "positive": lambda it: "clinical_lab" in it.labels,
                "keywords": corpus.ACCOUNT_KEYWORDS})
    return out


# ── answer cache ─────────────────────────────────────────────────────────

def load(scorer: str) -> dict[tuple, dict]:
    path = ANSWERS / f"{scorer}.jsonl"
    seen: dict[tuple, dict] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            row = json.loads(line)
            seen[(row["variant"], row["key"], row["item"])] = row
    return seen


def append(scorer: str, rows: list[dict]) -> None:
    ANSWERS.mkdir(parents=True, exist_ok=True)
    with (ANSWERS / f"{scorer}.jsonl").open("a") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


# ── scorers ──────────────────────────────────────────────────────────────

def _post(url: str, body: dict, key: str | None, timeout: float) -> tuple[int, dict, int]:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, payload = r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        status, payload = exc.code, {"error": exc.read().decode(errors="replace")[:300]}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        status, payload = 0, {"error": type(exc).__name__}
    return status, payload, round((time.perf_counter() - t0) * 1000)


def _retry(call, attempts: int = 3):
    for attempt in range(attempts):
        status, payload, ms = call()
        if status == 200:
            break
        time.sleep(1 + attempt)
    return status, payload, ms


def score_systemone(args, state: str, wording: str) -> dict:
    """One yes-no question to a Jev-protocol endpoint. Returns P(yes)."""
    if args.qtype == "choice":
        qs = {"q": {"type": "choice", "instructions": wording, "criteria": {"yes": "Yes.", "no": "No."}}}
    else:
        qs = {"q": {"type": "noul", "instructions": wording}}
    body = {"model": args.model, "state": state, "questions": qs, **json.loads(args.extra_body or "{}")}
    status, payload, ms = _retry(lambda: _post(args.url, body, args.key, args.timeout))
    ans = ((payload.get("answers") or payload.get("questions") or {}) if isinstance(payload, dict) else {}).get("q")
    p = None
    if isinstance(ans, dict):
        if isinstance(ans.get("noul"), (int, float)):
            p = float(ans["noul"])
        else:
            dist = ans.get("probabilities") or ans.get("distribution")
            if isinstance(dist, dict) and "yes" in dist:
                p = float(dist["yes"])
    usage = payload.get("usage") if isinstance(payload, dict) else None
    return {"p": p, "status": status, "ms": ms, "tokens": (usage or {}).get("input_tokens"),
            "cost": float((usage or {}).get("cost") or 0)}


_YES = {"yes", "y", "true"}
_NO = {"no", "n", "false"}


def score_logprob(args, state: str, wording: str) -> dict:
    """A chat model's P(yes) from the log-probabilities of its first answer token."""
    body = {"model": args.model, "max_tokens": 1, "temperature": 0, "logprobs": True, "top_logprobs": 20,
            "messages": [
                {"role": "system", "content": "Answer the question about the text with one word: yes or no."},
                {"role": "user", "content": f"{state}\n\nQuestion: {wording}\nAnswer (yes or no):"}],
            **json.loads(args.extra_body or "{}")}
    status, payload, ms = _retry(lambda: _post(args.url, body, args.key, args.timeout))
    p = None
    try:
        top = payload["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
        yes = sum(math.exp(t["logprob"]) for t in top if t["token"].strip().lower() in _YES)
        no = sum(math.exp(t["logprob"]) for t in top if t["token"].strip().lower() in _NO)
        if yes + no > 0:
            p = yes / (yes + no)
    except (KeyError, IndexError, TypeError):
        pass
    usage = payload.get("usage") if isinstance(payload, dict) else None
    return {"p": p, "status": status, "ms": ms, "tokens": (usage or {}).get("prompt_tokens"),
            "cost": float((usage or {}).get("cost") or 0)}


_EMBEDDED: dict[tuple[str, str], list[float]] = {}


def embed(args, texts: list[str], task: str) -> list[list[float]]:
    """Embeddings for `texts` as queries or documents; each distinct text is sent once per run."""
    prefix = args.query_prefix if task == "query" else args.doc_prefix
    missing = [t for t in dict.fromkeys(texts) if (task, t) not in _EMBEDDED]
    for i in range(0, len(missing), 32):
        batch = missing[i:i + 32]
        # Some servers apply the model's own retrieval prompts and want to be told what the text is for.
        inputs = [{"text": t, "task": task, "title": None} for t in batch] if args.input_objects \
            else [prefix + t for t in batch]
        status, payload, _ = _retry(lambda: _post(args.url, {"model": args.model, "input": inputs}, args.key, 120))
        if status != 200:
            raise SystemExit(f"embedding endpoint returned {status}: {payload}")
        for t, d in zip(batch, payload["data"]):
            _EMBEDDED[(task, t)] = d["embedding"]
    return [_EMBEDDED[(task, t)] for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1)


_STOP = set("a an and are as at be by do does for from has have in is it its of on or our that the their they this "
            "to was we with what which who whom whose these those any about us them than not been being".split())


def _tok(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP]


def bm25(query: str, docs: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    toks = [_tok(d) for d in docs]
    n, avg = len(docs), sum(map(len, toks)) / max(1, len(docs))
    df = Counter(t for ts in toks for t in set(ts))
    q = _tok(query)
    scores = []
    for ts in toks:
        tf = Counter(ts)
        s = 0.0
        for t in q:
            if tf[t]:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(ts) / avg))
        scores.append(s)
    return scores


# ── running a scorer ─────────────────────────────────────────────────────

def run(args) -> int:
    args.key = os.environ.get(args.key_env, "").strip() if args.key_env else None
    if args.key_env and not args.key:
        raise SystemExit(f"{args.key_env} is not set")
    seen = load(args.scorer)
    spent = [sum(r.get("cost") or 0 for r in seen.values())]  # counts what earlier runs of this scorer spent
    phases = [p for p in args.phases.split(",") if p]
    for phase in phases:
        split = "dev" if phase == "dev" else "held"
        variant = "reword" if phase == "reword" else "base"
        for spec in questions():
            if args.only and spec["key"] not in args.only.split(","):
                continue
            wording = spec["reworded"] if variant == "reword" else spec["q"]
            todo = [it for it in spec["items"] if it.split == split and (variant, spec["key"], it.id) not in seen]
            if not todo:
                continue
            t0 = time.perf_counter()
            if args.kind in ("systemone", "logprob"):
                fn = score_systemone if args.kind == "systemone" else score_logprob

                def one(it, spec=spec, wording=wording, fn=fn):
                    if spent[0] >= args.max_cost:
                        return None  # the spend cap was reached; the item stays unanswered
                    row = {"variant": variant, "key": spec["key"], "item": it.id,
                           **fn(args, spec["state"](it), wording)}
                    spent[0] += row.get("cost") or 0
                    return row

                rows = []
                with ThreadPoolExecutor(args.workers) as ex:
                    for i, row in enumerate(ex.map(one, todo), 1):
                        if row is not None and row.get("status") == 200:
                            rows.append(row)  # a failed call is not cached, so a rerun asks again
                        if len(rows) >= 50 or i == len(todo):  # flush often: a stopped run keeps its answers
                            append(args.scorer, rows)
                            rows = []
                if spent[0] >= args.max_cost:
                    print(f"{args.scorer}: stopped at the spend cap (${spent[0]:.4f} of ${args.max_cost})", flush=True)
                    return 1
            elif args.kind == "embed":
                query = spec["query"] if variant == "base" or spec["key"].startswith("promise") else wording
                qv = embed(args, [query], "query")[0]
                dv = embed(args, [it.text for it in todo], "document")
                append(args.scorer, [{"variant": variant, "key": spec["key"], "item": it.id, "p": cosine(qv, d),
                                      "status": 200} for it, d in zip(todo, dv)])
            elif args.kind == "bm25":
                query = spec["query"] if variant == "base" or spec["key"].startswith("promise") else wording
                # BM25 statistics come from the whole split, as a search index would have them.
                pool = [it for it in spec["items"] if it.split == split]
                scores = dict(zip((it.id for it in pool), bm25(query, [it.text for it in pool])))
                append(args.scorer, [{"variant": variant, "key": spec["key"], "item": it.id, "p": scores[it.id],
                                      "status": 200} for it in todo])
            elif args.kind == "keyword":
                if variant == "reword":
                    continue  # the terms do not change with the question's wording
                kw = [w.lower() for w in spec["keywords"]]
                append(args.scorer, [{"variant": variant, "key": spec["key"], "item": it.id, "status": 200,
                                      "p": 1.0 if any(w in it.text.lower() for w in kw) else 0.0} for it in todo])
            seen = load(args.scorer)
            print(f"{args.scorer} {phase:6} {spec['key']:14} {len(todo)} items in {time.perf_counter() - t0:.0f}s"
                  f", spent ${spent[0]:.4f}", flush=True)
    return 0


# ── metrics ──────────────────────────────────────────────────────────────

def auroc(scores: list[float], labels: list[bool]) -> float:
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def ranked(scores: list[float], labels: list[bool]) -> list[bool]:
    # Ties are broken pessimistically (negatives first), so a coarse scorer is not flattered.
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], labels[i]))
    return [labels[i] for i in order]


def avg_precision(scores, labels) -> float:
    hits, total = 0, 0.0
    for i, y in enumerate(ranked(scores, labels), 1):
        if y:
            hits += 1
            total += hits / i
    return total / max(1, sum(labels))


def found_at(scores, labels, k: int) -> int:
    return sum(ranked(scores, labels)[:k])


def fit_threshold(scores, labels) -> float:
    best, best_f1 = 0.5, -1.0
    for t in sorted(set(scores)):
        tp = sum(s >= t and y for s, y in zip(scores, labels))
        fp = sum(s >= t and not y for s, y in zip(scores, labels))
        fn = sum(s < t and y for s, y in zip(scores, labels))
        f1 = 2 * tp / max(1, 2 * tp + fp + fn)
        if f1 > best_f1:
            best, best_f1 = t, f1
    return best


def at_threshold(scores, labels, t) -> dict:
    tp = sum(s >= t and y for s, y in zip(scores, labels))
    fp = sum(s >= t and not y for s, y in zip(scores, labels))
    fn = sum(s < t and y for s, y in zip(scores, labels))
    return {"threshold": round(t, 4), "flagged": tp + fp, "precision": round(tp / max(1, tp + fp), 3),
            "recall": round(tp / max(1, tp + fn), 3)}


def summarize(scorer: str) -> dict:
    seen = load(scorer)
    out: dict = {"questions": {}}
    pooled = Counter()
    for spec in questions():
        key = spec["key"]

        def scored(split: str, variant: str):
            pairs = [(it, seen.get((variant, key, it.id))) for it in spec["items"] if it.split == split]
            return [(it, r["p"]) for it, r in pairs if r and r.get("p") is not None], len(pairs)

        dev, _ = scored("dev", "base")
        held, held_n = scored("held", "base")
        if not held:
            continue
        hs, hy = [p for _, p in held], [spec["positive"](it) for it, _ in held]
        # Positives are counted over every held-out item, so an unanswered positive is a miss.
        all_pos = sum(spec["positive"](it) for it in spec["items"] if it.split == "held")
        q: dict = {"held_items": held_n, "held_answered": len(held), "held_positives": all_pos,
                   "auroc": round(auroc(hs, hy), 3), "ap": round(avg_precision(hs, hy), 3),
                   "found@10": found_at(hs, hy, 10), "found@25": found_at(hs, hy, 25),
                   "distinct_scores": len(set(hs))}
        t = None
        if dev:
            t = fit_threshold([p for _, p in dev], [spec["positive"](it) for it, _ in dev])
            q["at_dev_threshold"] = at_threshold(hs, hy, t)
        reword, _ = scored("held", "reword")
        if reword:
            base = dict((it.id, p) for it, p in held)
            both = [(it, base[it.id], p) for it, p in reword if it.id in base]
            rs, ry = [p for _, _, p in both], [spec["positive"](it) for it, _, _ in both]
            q["reworded"] = {"auroc": round(auroc(rs, ry), 3), "found@10": found_at(rs, ry, 10)}
            if t is not None:
                q["reworded"]["flips_at_dev_threshold"] = sum((b >= t) != (r >= t) for _, b, r in both)
                q["reworded"]["flagged"] = sum(r >= t for r in rs)
        out["questions"][key] = q
        pooled["positives"] += all_pos
        pooled["found@10"] += q["found@10"]
        pooled["found@25"] += q["found@25"]
        pooled["unanswered"] += held_n - len(held)
    out["pooled_held"] = dict(pooled)
    rows = [r for r in seen.values() if r.get("ms") is not None and r.get("status") == 200]
    if rows:
        ms = sorted(r["ms"] for r in rows)
        out["calls"] = {"answered": len(rows),
                        "failed": sum(1 for r in seen.values() if r.get("status") != 200),
                        "latency_ms_p50": ms[len(ms) // 2], "latency_ms_p95": ms[int(len(ms) * 0.95)],
                        "input_tokens_mean": round(statistics.mean(r.get("tokens") or 0 for r in rows)),
                        "cost_usd": round(sum(r.get("cost") or 0 for r in seen.values()), 4)}
    return out


def report(args) -> int:
    skip = set((args.skip or "").split(","))
    scorers = sorted(p.stem for p in ANSWERS.glob("*.jsonl") if p.stem not in skip)
    full = {s: summarize(s) for s in scorers}
    REPORT.write_text(json.dumps(full, indent=1, sort_keys=True) + "\n")
    keys = [spec["key"] for spec in questions()]
    print("Held-out positives found in the top 10 (of positives), per question, then pooled; AUROC in brackets.\n")
    print("| scorer | " + " | ".join(keys) + " | pooled @10 | pooled @25 | p50 ms |")
    print("|---|" + "---|" * (len(keys) + 3))
    for s in scorers:
        r = full[s]
        cells = []
        for k in keys:
            q = r["questions"].get(k)
            cells.append(f"{q['found@10']}/{q['held_positives']} ({q['auroc']:.3f})" if q else "—")
        pool = r["pooled_held"]
        print(f"| {s} | " + " | ".join(cells) +
              f" | {pool.get('found@10', 0)}/{pool.get('positives', 0)}"
              f" | {pool.get('found@25', 0)}/{pool.get('positives', 0)}"
              f" | {r.get('calls', {}).get('latency_ms_p50', '—')} |")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--scorer", required=True, help="name for this run; answers go to results/answers/<name>.jsonl")
    r.add_argument("--kind", required=True, choices=["systemone", "logprob", "embed", "bm25", "keyword"])
    r.add_argument("--url")
    r.add_argument("--model")
    r.add_argument("--key-env", help="environment variable holding the API key, if the endpoint needs one")
    r.add_argument("--qtype", choices=["noul", "choice"], default="noul")
    r.add_argument("--extra-body", help='JSON merged into each request, e.g. \'{"provider": {"zdr": true}}\'')
    r.add_argument("--query-prefix", default="")
    r.add_argument("--doc-prefix", default="")
    r.add_argument("--input-objects", action="store_true",
                   help="send embedding inputs as {text, task} objects instead of prefixed strings")
    r.add_argument("--phases", default="held,dev,reword")
    r.add_argument("--only", help="comma-separated question keys")
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--timeout", type=float, default=60.0)
    r.add_argument("--max-cost", type=float, default=1.0, help="stop when this scorer has spent this many dollars")
    r.set_defaults(fn=run)
    rep = sub.add_parser("report")
    rep.add_argument("--skip", help="comma-separated scorers to leave out, e.g. one whose run is unfinished")
    rep.set_defaults(fn=report)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
