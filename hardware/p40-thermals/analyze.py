#!/usr/bin/env python3
"""Join llama-server request timings with GPU temperature samples (Tesla P40).

Standard library only. Reads three things that already exist on the box:

  --samples   CSV from a 30 s nvidia-smi sampler with columns
              timestamp_utc, temperature_gpu, utilization_gpu, power_draw,
              memory_used, clocks_sm, pstate (extra columns are ignored)
  --log       one or more llama-server log files written with
              `--log-file ... -lv 4` (plain or .gz). Their timestamps are
              relative to process start, so each log is anchored to wall time
              by matching its requests against the proxy's access log.
  --access    the proxy access log: lines that start with an ISO-8601
              timestamp (with offset) and end with the request duration, e.g.
              `journalctl -u llama-swap -o short-iso-precise | grep chat/completions`

Subcommands:
  report   print the anchoring result and the temperature-bin tables
  table    write the aggregate tables as CSV (per-request rows only with --per-request)

Nothing from a prompt, a client address or a hostname is read into the output.
"""
import argparse
import bisect
import csv
import gzip
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

REL = r"(\d+)\.(\d+)\.(\d+)\.(\d+)"
PP_RE = re.compile(REL + r" I slot print_timing: id +\d+ \| task (\d+) \| prompt eval time = +([\d.]+) ms / +(\d+) tokens")
TG_RE = re.compile(REL + r" I slot print_timing: id +\d+ \| task (\d+) \| +eval time = +([\d.]+) ms / +(\d+) tokens")
TOT_RE = re.compile(REL + r" I slot print_timing: id +\d+ \| task (\d+) \| +total time = +([\d.]+) ms")
HDR_RE = re.compile(REL + r" I cmn  common_param: common_params_print_info: build")
DUR_RE = re.compile(r"(?:(\d+)m)?([\d.]+)(ms|µs|s)$")


def rel_seconds(m):
    mi, s, ms, us = (int(x) for x in m.groups()[:4])
    return mi * 60 + s + ms / 1e3 + us / 1e6


def open_text(path):
    return gzip.open(path, "rt", errors="replace") if path.endswith(".gz") else open(path, errors="replace")


def parse_log(path):
    """Yield segments (one per llama-server start) of completed requests."""
    segments, cur = [], None
    for line in open_text(path):
        if HDR_RE.match(line):
            cur = {"source": path, "tasks": {}}
            segments.append(cur)
            continue
        if cur is None:
            continue
        for kind, rx in (("pp", PP_RE), ("tg", TG_RE), ("tot", TOT_RE)):
            m = rx.match(line)
            if m:
                task = int(m.group(5))
                t = cur["tasks"].setdefault(task, {})
                if kind == "tot":
                    t["end_rel"] = rel_seconds(m)
                    t["total_ms"] = float(m.group(6))
                else:
                    t[kind + "_ms"] = float(m.group(6))
                    t[kind + "_n"] = int(m.group(7))
                break
    for seg in segments:
        seg["tasks"] = [dict(task=k, **v) for k, v in seg["tasks"].items()
                        if {"end_rel", "total_ms", "pp_ms", "tg_ms"} <= v.keys()]
    return [s for s in segments if s["tasks"]]


def parse_access(path):
    rows = []
    for line in open_text(path):
        parts = line.split()
        if not parts:
            continue
        try:
            ts = datetime.fromisoformat(parts[0]).astimezone(timezone.utc)
        except ValueError:
            continue
        m = DUR_RE.search(parts[-1])
        if not m:
            continue
        mins, val, unit = m.groups()
        dur = float(val) * {"s": 1, "ms": 1e-3, "µs": 1e-6}[unit] + (int(mins) * 60 if mins else 0)
        rows.append((ts.timestamp(), dur))
    rows.sort()
    return rows


def anchor(seg, access, dur_tol=0.5, end_tol=3.0):
    """Find process start (epoch) such that start + end_rel lines up with access-log ends."""
    by_dur = sorted((d, t) for t, d in access)
    durs = [d for d, _ in by_dur]
    votes = Counter()
    for t in seg["tasks"]:
        tot = t["total_ms"] / 1e3
        lo = bisect.bisect_left(durs, tot - dur_tol)
        hi = bisect.bisect_right(durs, tot + dur_tol + 1.0)  # proxy adds a little overhead
        for d, ts in by_dur[lo:hi]:
            votes[round(ts - t["end_rel"])] += 1
    if not votes:
        return None, 0, 0
    # merge neighbouring 1 s bins
    best, score = max(((o, sum(votes.get(o + k, 0) for k in range(-2, 3))) for o in votes), key=lambda x: x[1])
    ends = sorted(ts for ts, _ in access)
    matched = 0
    for t in seg["tasks"]:
        e = best + t["end_rel"]
        i = bisect.bisect_left(ends, e - end_tol)
        if i < len(ends) and ends[i] <= e + end_tol:
            matched += 1
    return best, score, matched


def load_samples(path):
    out = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f, skipinitialspace=True):
            try:
                ts = datetime.strptime(r["timestamp_utc"].strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
                out.append((ts, int(r["temperature_gpu"]), int(r["utilization_gpu"]), float(r["power_draw"]),
                            int(r["clocks_sm"]), r["pstate"].strip()))
            except (KeyError, ValueError, TypeError):
                continue
    out.sort()
    return out


def window(samples, keys, a, b, pad=16.0):
    """Samples inside [a, b]; if none, the single nearest within pad seconds."""
    i, j = bisect.bisect_left(keys, a), bisect.bisect_right(keys, b)
    if j > i:
        return samples[i:j]
    c = bisect.bisect_left(keys, (a + b) / 2)
    best = [s for s in samples[max(0, c - 1):c + 1] if abs(s[0] - (a + b) / 2) <= pad + (b - a) / 2]
    return best[:1]


def build_rows(args):
    access = parse_access(args.access)
    samples = load_samples(args.samples)
    keys = [s[0] for s in samples]
    rows, anchors = [], []
    for path in args.log:
        for seg in parse_log(path):
            start, score, matched = anchor(seg, access)
            anchors.append((len(seg["tasks"]), score, matched, start))
            if start is None or matched < 0.8 * len(seg["tasks"]):
                continue
            for t in seg["tasks"]:
                end = start + t["end_rel"]
                tg_start = end - t["tg_ms"] / 1e3
                pp_start = tg_start - t["pp_ms"] / 1e3
                pw = window(samples, keys, pp_start, tg_start)
                tw = window(samples, keys, tg_start, end)
                if not pw or not tw:
                    continue
                rows.append({
                    "utc": datetime.fromtimestamp(end, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "pp_tokens": t["pp_n"], "pp_tps": round(t["pp_n"] / (t["pp_ms"] / 1e3), 2) if t["pp_ms"] else "",
                    "tg_tokens": t["tg_n"], "tg_tps": round(t["tg_n"] / (t["tg_ms"] / 1e3), 2) if t["tg_ms"] else "",
                    "pp_temp_max": max(s[1] for s in pw), "pp_sm_min": min(s[4] for s in pw),
                    "pp_power_mean": round(statistics.mean(s[3] for s in pw), 1),
                    "tg_temp_max": max(s[1] for s in tw), "tg_sm_min": min(s[4] for s in tw),
                    "tg_power_mean": round(statistics.mean(s[3] for s in tw), 1),
                    "pstate": "/".join(sorted({s[5] for s in pw + tw})),
                })
    return rows, anchors, samples


def tbin(t, width):
    lo = (t // width) * width
    return f"{lo}-{lo + width - 1}"


def aggregate(rows, phase, width, min_tokens):
    groups = defaultdict(list)
    for r in rows:
        if r[f"{phase}_tps"] == "" or r[f"{phase}_tokens"] < min_tokens:
            continue
        clock = "full" if r[f"{phase}_sm_min"] > 1000 else "capped<=544" if r[f"{phase}_sm_min"] <= 544 else "mid"
        groups[(tbin(r[f"{phase}_temp_max"], width), clock)].append(r)
    out = []
    for (b, clock), rs in sorted(groups.items(), key=lambda kv: (int(kv[0][0].split("-")[0]), kv[0][1])):
        v = [r[f"{phase}_tps"] for r in rs]
        out.append({"phase": phase, "temp_bin_c": b, "sm_clock": clock, "n": len(v),
                    "median_tps": round(statistics.median(v), 1),
                    "p10_tps": round(sorted(v)[int(0.1 * (len(v) - 1))], 1),
                    "p90_tps": round(sorted(v)[int(0.9 * (len(v) - 1))], 1),
                    "median_tokens": int(statistics.median(r[f"{phase}_tokens"] for r in rs)),
                    "median_sm_mhz": int(statistics.median(r[f"{phase}_sm_min"] for r in rs)),
                    "median_power_w": round(statistics.median(r[f"{phase}_power_mean"] for r in rs), 1)})
    return out


def busy_profile(samples, width):
    """All sampled time with the GPU busy (util >= 90%): SM clock and power by temperature."""
    g = defaultdict(list)
    for ts, temp, util, pw, sm, ps in samples:
        if util >= 90:
            g[tbin(temp, width)].append((sm, pw))
    out = []
    for b, v in sorted(g.items(), key=lambda kv: int(kv[0].split("-")[0])):
        sms = [x[0] for x in v]
        out.append({"temp_bin_c": b, "samples": len(v),
                    "median_sm_mhz": int(statistics.median(sms)),
                    "share_sm_le_544": round(sum(1 for s in sms if s <= 544) / len(v), 3),
                    "median_power_w": round(statistics.median(x[1] for x in v), 1)})
    return out


def idle_profile(samples):
    """Samples at 0% utilisation, split by performance state and SM clock."""
    g = defaultdict(list)
    for ts, temp, util, pw, sm, ps in samples:
        if util == 0:
            g[(ps, "544" if sm <= 544 else ">544")].append((temp, pw))
    out = []
    for (ps, sm), v in sorted(g.items()):
        t = sorted(x[0] for x in v)
        out.append({"pstate": ps, "sm_mhz": sm, "samples": len(v),
                    "median_temp_c": statistics.median(t), "p90_temp_c": t[int(0.9 * (len(t) - 1))],
                    "median_power_w": round(statistics.median(x[1] for x in v), 1)})
    return out


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def print_table(rows):
    if not rows:
        print("  (none)")
        return
    cols = list(rows[0].keys())
    print("  " + " | ".join(cols))
    for r in rows:
        print("  " + " | ".join(str(r[c]) for c in cols))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["report", "table"])
    ap.add_argument("--samples", required=True)
    ap.add_argument("--log", required=True, nargs="+")
    ap.add_argument("--access", required=True)
    ap.add_argument("--bin", type=int, default=5, help="temperature bin width, C")
    ap.add_argument("--min-pp", type=int, default=512, help="ignore prefills shorter than this")
    ap.add_argument("--min-tg", type=int, default=128, help="ignore generations shorter than this")
    ap.add_argument("--out", default=".", help="output directory for `table`")
    ap.add_argument("--per-request", action="store_true",
                    help="also write per-request rows (timestamps + token counts); off by default")
    args = ap.parse_args()

    rows, anchors, samples = build_rows(args)
    pp = aggregate(rows, "pp", args.bin, args.min_pp)
    tg = aggregate(rows, "tg", args.bin, args.min_tg)
    busy = busy_profile(samples, args.bin)
    idle = idle_profile(samples)

    if args.cmd == "report":
        print("anchoring (tasks, votes, matched, start):")
        for n, score, matched, start in anchors:
            s = datetime.fromtimestamp(start, timezone.utc).isoformat() if start else None
            print(f"  {n} tasks, {score} votes, {matched} matched, start {s}")
        print(f"joined requests: {len(rows)}"
              + (f" ({rows[0]['utc']} .. {rows[-1]['utc']})" if rows else ""))
        print(f"\nprefill tokens/s by max GPU temp during prefill (prefill >= {args.min_pp} tokens):")
        print_table(pp)
        print(f"\ndecode tokens/s by max GPU temp during decode (>= {args.min_tg} tokens):")
        print_table(tg)
        print(f"\nall samples at >= 90% utilisation, {datetime.fromtimestamp(samples[0][0], timezone.utc):%Y-%m-%d}"
              f" .. {datetime.fromtimestamp(samples[-1][0], timezone.utc):%Y-%m-%d}:")
        print_table(busy)
        print("\nidle samples (0% utilisation) by performance state:")
        print_table(idle)
    else:
        if args.per_request:
            write_csv(f"{args.out}/requests.csv", rows)
        write_csv(f"{args.out}/speed_by_temp.csv", pp + tg)
        write_csv(f"{args.out}/busy_clock_by_temp.csv", busy)
        write_csv(f"{args.out}/idle_by_pstate.csv", idle)
        print(f"wrote {len(rows)} requests, {len(pp) + len(tg)} speed bins, {len(busy)} clock bins,"
              f" {len(idle)} idle rows to {args.out}")


if __name__ == "__main__":
    sys.exit(main())
