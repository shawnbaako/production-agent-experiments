#!/usr/bin/env python3
"""Run a fixed public query set against a SearXNG instance with several engine mixes, with and
without a date filter, and record which engines answered and how many results were on topic.

  python3 mix.py run --url http://127.0.0.1:8080
  python3 mix.py run --url http://127.0.0.1:8080 --time-range week
  python3 mix.py report

The instance needs `json` in `search.formats`. Engines are chosen per request with the `engines`
parameter, so the mixes do not depend on which engines the instance enables; an engine marked
`inactive` in the instance's settings is not loaded and cannot be chosen. Engine weights are the
instance's own and are not set here.

Every answer is cached in results/searches.jsonl (one line per mix, time range and query) and a
re-run skips what is cached. A request that fails at the HTTP level is not cached. The instance's
/config is saved to results/config.json. Standard library only; no model is called.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from queries import QUERIES  # noqa: E402

RESULTS = HERE / "results"
CACHE = RESULTS / "searches.jsonl"
TOP = 5
KEEP = ("url", "title", "content", "engine", "engines", "positions", "score", "publishedDate", "category")

SINGLES = ["bing", "duckduckgo web", "duckduckgo", "yandex", "google", "google cse", "brave", "qwant",
           "yahoo", "wikipedia"]
MIXES = {
    # The general engines a stock instance of the tested version enables, without the currency and
    # translation helpers.
    "stock general": ["duckduckgo", "google cse", "brave", "wikipedia", "wikidata"],
    "bing + ddg web": ["bing", "duckduckgo web"],
    "ddg web + yandex": ["duckduckgo web", "yandex"],
    "bing + ddg web + yandex": ["bing", "duckduckgo web", "yandex"],
}
RANGE_DAYS = {"day": 1, "week": 7, "month": 31, "year": 366}


def all_mixes() -> dict[str, list[str]]:
    out = {name: [name] for name in SINGLES}
    out.update(MIXES)
    return out


def load() -> dict[tuple, dict]:
    rows = {}
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            r = json.loads(line)
            rows[(r["mix"], r["time_range"], r["qid"])] = r
    return rows


def get_json(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "search-engine-mix-study/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run(args) -> None:
    RESULTS.mkdir(exist_ok=True)
    base = args.url.rstrip("/")
    config = get_json(f"{base}/config", args.timeout)
    tr_support = {e["name"]: bool(e.get("time_range_support")) for e in config.get("engines", [])}
    (RESULTS / "config.json").write_text(json.dumps({
        "version": config.get("version"),
        "engines": [{k: e.get(k) for k in ("name", "enabled", "categories", "time_range_support", "paging")}
                    for e in config.get("engines", [])],
    }, indent=1) + "\n")
    mixes = all_mixes()
    if args.mix:
        mixes = {k: v for k, v in mixes.items() if k in args.mix}
    missing = sorted({e for v in mixes.values() for e in v if e not in tr_support})
    if missing:
        print(f"not loaded on this instance, requests will name them anyway: {', '.join(missing)}")
    cached = load()
    sent = 0
    with CACHE.open("a") as out:
        for q in QUERIES:
            for mix, engines in mixes.items():
                for tr in ("", args.time_range):
                    if (mix, tr, q["id"]) in cached:
                        continue
                    if sent >= args.max_requests:
                        print(f"stopped at --max-requests {args.max_requests}")
                        return
                    params = {"q": q["q"], "format": "json", "engines": ",".join(engines),
                              "language": "en-US", "safesearch": "0"}
                    if tr:
                        params["time_range"] = tr
                    url = f"{base}/search?{urllib.parse.urlencode(params)}"
                    started = time.time()
                    try:
                        data = get_json(url, args.timeout)
                    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                        print(f"failed, not cached: {mix} {tr or '-'} {q['id']}: {exc}")
                        sent += 1
                        time.sleep(args.pause)
                        continue
                    sent += 1
                    row = {
                        "mix": mix, "engines_requested": engines, "time_range": tr, "qid": q["id"],
                        "query": q["q"], "version": config.get("version"),
                        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "seconds": round(time.time() - started, 2),
                        "results": [{k: r.get(k) for k in KEEP} for r in data.get("results", [])],
                        "unresponsive_engines": data.get("unresponsive_engines", []),
                        "infobox_engines": sorted({i.get("engine") for i in data.get("infoboxes", []) if i.get("engine")}),
                        "number_of_results": data.get("number_of_results"),
                    }
                    out.write(json.dumps(row) + "\n")
                    out.flush()
                    answered = sorted({e for r in row["results"] for e in (r.get("engines") or [])})
                    print(f"{q['id']} {mix:<26} {tr or '-':<6} {len(row['results']):>3} results, "
                          f"answered: {', '.join(answered) or 'none'}")
                    # A filtered request whose engines all lack time-range support makes no outbound
                    # request, so it needs no pause.
                    if not (tr and not any(tr_support.get(e, True) for e in engines)):
                        time.sleep(args.pause)


def on_topic(result: dict, must: list[list[str]]) -> bool:
    text = " ".join(str(result.get(k) or "") for k in ("title", "content", "url")).lower()
    return all(any(alt in text for alt in group) for group in must)


def in_range(result: dict, tr: str, fetched_at: str) -> bool | None:
    raw = result.get("publishedDate")
    if not raw or not tr:
        return None
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d >= datetime.fromisoformat(fetched_at) - timedelta(days=RANGE_DAYS[tr])


def summarise(rows: list[dict], must: dict[str, list], tr_support: dict[str, bool]) -> dict:
    n = len(rows)
    skipped = Counter()
    answered_counts, top, on, dated, inside = [], 0, 0, 0, 0
    silent = Counter()
    unresponsive = Counter()
    silent_searches = 0
    for r in rows:
        answered = {e for x in r["results"] for e in (x.get("engines") or [])}
        failed = {u[0] for u in r["unresponsive_engines"]}
        # wikipedia and wikidata answer with an infobox, not with results.
        answered_box = set(r.get("infobox_engines", []))
        for u in r["unresponsive_engines"]:
            unresponsive[f"{u[0]}: {u[1]}"] += 1
        # Not queried at all: a date filter and no time-range support (SearXNG drops it before the
        # request). Everything else that is neither an answer nor an error found nothing.
        dropped = [e for e in r["engines_requested"]
                   if r["time_range"] and not tr_support.get(e, True) and e not in failed]
        skipped.update(dropped)
        quiet = [e for e in r["engines_requested"] if e not in answered | answered_box | failed | set(dropped)]
        silent.update(quiet)
        silent_searches += bool(dropped)
        answered_counts.append(len(answered))
        for x in r["results"][:TOP]:
            top += 1
            on += on_topic(x, must[r["qid"]])
            ok = in_range(x, r["time_range"], r["fetched_at"])
            if ok is not None:
                dated += 1
                inside += ok
    return {
        "searches": n,
        "empty": sum(1 for c in answered_counts if c == 0),
        "mean_engines_answering": round(sum(answered_counts) / n, 2) if n else None,
        "answered_by_two_or_more": sum(1 for c in answered_counts if c >= 2),
        "top_results": top,
        "on_topic_top": on,
        "on_topic_pct": round(100 * on / top, 1) if top else None,
        "searches_with_engine_skipped": silent_searches,
        "skipped_by_engine": dict(skipped.most_common()),
        "empty_without_error_by_engine": dict(silent.most_common()),
        "unresponsive": dict(unresponsive.most_common()),
        "dated_top": dated,
        "dated_in_range": inside,
    }


def report(args) -> None:
    rows = list(load().values())
    must = {q["id"]: q["must"] for q in QUERIES}
    kinds = {q["id"]: q["kind"] for q in QUERIES}
    config = json.loads((RESULTS / "config.json").read_text())
    tr_support = {e["name"]: bool(e["time_range_support"]) for e in config["engines"]}
    order = list(all_mixes())
    groups = defaultdict(list)
    for r in rows:
        groups[(r["mix"], r["time_range"])].append(r)
        groups[(r["mix"], r["time_range"], kinds[r["qid"]])].append(r)
    out = {"version": sorted({r["version"] for r in rows}), "top": TOP,
           "fetched": [min(r["fetched_at"] for r in rows), max(r["fetched_at"] for r in rows)] if rows else None,
           "by_mix": {}, "by_mix_and_kind": {}}
    for key, rs in sorted(groups.items(), key=lambda kv: (order.index(kv[0][0]) if kv[0][0] in order else 99, kv[0][1:])):
        label = f"{key[0]} | {key[1] or 'none'}"
        if len(key) == 2:
            out["by_mix"][label] = summarise(rs, must, tr_support)
        else:
            out["by_mix_and_kind"][f"{label} | {key[2]}"] = summarise(rs, must, tr_support)
    (RESULTS / "report.json").write_text(json.dumps(out, indent=1) + "\n")

    print(f"SearXNG {', '.join(out['version'])}; fetched {out['fetched'][0]} to {out['fetched'][1]}\n")
    print("| Mix | Date filter | Searches | Empty | Engines answering (mean) | Answered by 2+ "
          "| On topic, top 5 | Searches with an engine skipped, unreported |")
    print("|---|---|---|---|---|---|---|---|")
    for label, s in out["by_mix"].items():
        mix, tr = label.split(" | ")
        print(f"| {mix} | {tr} | {s['searches']} | {s['empty']} | {s['mean_engines_answering']} "
              f"| {s['answered_by_two_or_more']} | {s['on_topic_pct']}% ({s['on_topic_top']}/{s['top_results']}) "
              f"| {s['searches_with_engine_skipped']} |")
    print("\nUnresponsive engines as reported by SearXNG, per mix and date filter:")
    for label, s in out["by_mix"].items():
        if s["unresponsive"]:
            print(f"- {label}: " + "; ".join(f"{k} x{v}" for k, v in s["unresponsive"].items()))
    print("\nEngines skipped by the date filter (not queried, not in unresponsive_engines):")
    for label, s in out["by_mix"].items():
        if s["skipped_by_engine"]:
            print(f"- {label}: " + "; ".join(f"{k} x{v}" for k, v in s["skipped_by_engine"].items()))
    print("\nEngines queried that returned nothing and no error:")
    for label, s in out["by_mix"].items():
        if s["empty_without_error_by_engine"]:
            print(f"- {label}: " + "; ".join(f"{k} x{v}" for k, v in s["empty_without_error_by_engine"].items()))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--url", required=True, help="SearXNG base URL, e.g. http://127.0.0.1:8080")
    r.add_argument("--time-range", default="month", choices=sorted(RANGE_DAYS))
    r.add_argument("--mix", action="append", help="run only this mix (repeatable)")
    r.add_argument("--pause", type=float, default=2.0, help="seconds between requests that reach engines")
    r.add_argument("--timeout", type=float, default=30.0)
    r.add_argument("--max-requests", type=int, default=700)
    sub.add_parser("report")
    args = p.parse_args()
    run(args) if args.cmd == "run" else report(args)


if __name__ == "__main__":
    main()
