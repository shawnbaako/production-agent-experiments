#!/usr/bin/env python3
"""Route a delegated assignment to a specialist: a decision model against a keyword rule and a fixed default.

Cases and question wordings are in cases.py. Two offered sets are scored:

  prod  general, draft          what the production system could actually offer a tool-using sub-task
  full  general, research, draft, meeting

and for each, the production question (v1), a rewording, the options in reverse order, and a second
question (v2). An answer of "unsure", or no answer, runs on `general`, as production did.

  OPENROUTER_API_KEY=... python3 route.py run --scorer jev-1.14 --model typesafe/jev-1.14
  python3 route.py report

Answers are cached in results/<scorer>.jsonl; the report can be recomputed without any call.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cases as C  # noqa: E402

RESULTS = HERE / "results"
PROD = ["general", "draft"]
FULL = ["general", "research", "draft", "meeting"]
SPECIALIST = {"research", "draft", "meeting"}


def load_cases() -> list[dict]:
    return [{"cid": f"s{i:03d}", "ref": ref, "assignment": a, "expected": e,
             "split": "dev" if i % 3 == 0 else "held"} for i, (ref, a, e) in enumerate(C.CASES)]


def state(c: dict) -> str:
    return f"Assignment:\n{c['assignment']}\n\nRequired output:\n{c['expected']}"


def runs() -> dict[str, tuple[str, dict, list[str]]]:
    """Run name -> (question, criteria, option order)."""
    def crit(src, offered):
        return {p: src[p] for p in offered} | {"unsure": src["unsure"]}

    def rev(xs):
        return list(reversed(xs + ["unsure"]))
    return {
        "v1_prod": (C.V1_QUESTION, crit(C.V1_CRITERIA, PROD), PROD + ["unsure"]),
        "v1_full": (C.V1_QUESTION, crit(C.V1_CRITERIA, FULL), FULL + ["unsure"]),
        "v1_prod_reworded": (C.V1_REWORDED, crit(C.V1_CRITERIA, PROD), PROD + ["unsure"]),
        "v1_prod_reordered": (C.V1_QUESTION, crit(C.V1_CRITERIA, PROD), rev(PROD)),
        "v1_full_reworded": (C.V1_REWORDED, crit(C.V1_CRITERIA, FULL), FULL + ["unsure"]),
        "v1_full_reordered": (C.V1_QUESTION, crit(C.V1_CRITERIA, FULL), rev(FULL)),
        "v2_prod": (C.V2_QUESTION, crit(C.V2_CRITERIA, PROD), PROD + ["unsure"]),
        "v2_full": (C.V2_QUESTION, crit(C.V2_CRITERIA, FULL), FULL + ["unsure"]),
        "v2_full_reordered": (C.V2_QUESTION, crit(C.V2_CRITERIA, FULL), rev(FULL)),
    }


def offered_of(run: str) -> list[str]:
    return PROD if "_prod" in run else FULL


def load(scorer: str) -> dict[tuple, dict]:
    path = RESULTS / f"{scorer}.jsonl"
    rows = {}
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            rows[(r["run"], r["cid"])] = r
    return rows


def ask(args, key: str, run: str, spec, c: dict) -> dict:
    q, crit, order = spec
    body = {"model": args.model, "state": state(c),
            "questions": {"specialty": {"type": "choice", "instructions": q,
                                        "criteria": {k: crit[k] for k in order}}}}
    req = urllib.request.Request(args.url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
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
    ans = ((payload.get("answers") or {}) if isinstance(payload, dict) else {}).get("specialty") or {}
    dist = ans.get("probabilities") or ans.get("distribution")
    choice = ans.get("choice")
    p = float(dist[choice]) if isinstance(dist, dict) and choice in dist else None
    usage = payload.get("usage") or {}
    return {"run": run, "cid": c["cid"], "choice": choice, "p": p, "status": status,
            "ms": round((time.perf_counter() - t0) * 1000), "cost": float(usage.get("cost") or 0)}


def run(args) -> int:
    key = os.environ.get(args.key_env, "").strip()
    if not key:
        raise SystemExit(f"{args.key_env} is not set")
    RESULTS.mkdir(exist_ok=True)
    seen = load(args.scorer)
    todo = [(name, spec, c) for name, spec in runs().items() for c in load_cases() if (name, c["cid"]) not in seen]
    with ThreadPoolExecutor(args.workers) as ex, (RESULTS / f"{args.scorer}.jsonl").open("a") as f:
        for row in ex.map(lambda t: ask(args, key, *t), todo):
            if row["status"] == 200:
                f.write(json.dumps(row, sort_keys=True) + "\n")
    rows = load(args.scorer)
    print(f"{args.scorer}: {len(rows)} answers, ${sum(r['cost'] for r in rows.values()):.4f}")
    return 0


# ── baselines and scoring ────────────────────────────────────────────────

def rule(c: dict, offered: list[str]) -> str:
    """A keyword rule on the required output, written once before scoring."""
    e, t = c["expected"].lower(), (c["assignment"] + " " + c["expected"]).lower()
    if "draft" in offered and any(w in e for w in ("email", "letter", "message", "reply", "note for review")):
        return "draft"
    if "meeting" in offered and ("transcript" in t or "minutes" in t) and "meeting" in e:
        return "meeting"
    if "research" in offered and any(w in e for w in ("source", "cited", "citation", "dossier")):
        return "research"
    return "general"


def effective(choice: str | None) -> str:
    """What runs: unsure or no usable answer falls to general."""
    return "general" if choice in (None, "unsure") else choice


def target(c: dict, offered: list[str]) -> str:
    """The best offered profile by intent; a specialty that is not offered falls to general."""
    return c["ref"] if c["ref"] in offered else "general"


def score(cs: list[dict], picks: dict[str, str | None], offered: list[str]) -> dict:
    ok = under = over = cross = 0
    for c in cs:
        eff, tgt = effective(picks.get(c["cid"])), target(c, offered)
        ok += eff == tgt
        under += tgt in SPECIALIST and eff == "general"
        over += tgt == "general" and eff in SPECIALIST
        cross += tgt in SPECIALIST and eff in SPECIALIST and eff != tgt
    return {"n": len(cs), "accuracy": round(ok / len(cs), 3), "under_routed": under, "over_routed": over,
            "specialist_mix_ups": cross}


def report(_args) -> int:
    held = [c for c in load_cases() if c["split"] == "held"]
    out: dict = {"held_out_cases": len(held)}
    lines = []
    for name, offered in (("prod", PROD), ("full", FULL)):
        base = {"keyword rule": score(held, {c["cid"]: rule(c, offered) for c in held}, offered),
                "fixed general": score(held, {c["cid"]: "general" for c in held}, offered)}
        out[name] = {"baselines": base}
        for label, s in base.items():
            lines.append((name, label, "—", s))
    for path in sorted(RESULTS.glob("*.jsonl")):
        rows = load(path.stem)
        ms = sorted(r["ms"] for r in rows.values())
        out.setdefault("scorers", {})[path.stem] = {"answers": len(rows), "latency_ms_p50": ms[len(ms) // 2],
                                                    "cost_usd": round(sum(r["cost"] for r in rows.values()), 4)}
        for run_name in runs():
            picks = {cid: r["choice"] for (rn, cid), r in rows.items() if rn == run_name}
            if not picks:
                continue
            s = score(held, picks, offered_of(run_name))
            base_run = run_name.replace("_reworded", "").replace("_reordered", "")
            if base_run != run_name:
                basepicks = {cid: r["choice"] for (rn, cid), r in rows.items() if rn == base_run}
                s["changed_vs_base"] = sum(effective(picks.get(c["cid"])) != effective(basepicks.get(c["cid"]))
                                           for c in held)
            out.setdefault(offered_of(run_name) is PROD and "prod" or "full", {}).setdefault(path.stem, {})[run_name] = s
            lines.append(("prod" if offered_of(run_name) is PROD else "full", f"{path.stem} {run_name}", "", s))
    (RESULTS / "report.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"Held-out cases: {len(held)}\n")
    print("| offered | selector | accuracy | under-routed | over-routed | mix-ups | answers changed vs base |")
    print("|---|---|---|---|---|---|---|")
    for name, label, _, s in sorted(lines, key=lambda x: (x[0], x[1])):
        print(f"| {name} | {label} | {s['accuracy']:.1%} | {s['under_routed']} | {s['over_routed']} | "
              f"{s['specialist_mix_ups']} | {s.get('changed_vs_base', '—')} |")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--scorer", required=True)
    r.add_argument("--model", required=True)
    r.add_argument("--url", default="https://openrouter.ai/api/v1/systemone")
    r.add_argument("--key-env", default="OPENROUTER_API_KEY")
    r.add_argument("--workers", type=int, default=8)
    r.set_defaults(fn=run)
    sub.add_parser("report").set_defaults(fn=report)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
