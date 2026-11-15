"""Score every arm on the same facts, with 95% bootstrap intervals over sources.

Universe: facts the extractor (or injection) marked ``observed`` that have a label. A fact is
"supported" when it is still ``observed`` after the quote check (baseline) and the arm did
not downgrade it. Arms only downgrade, so every arm is the baseline plus its check.

The same code scores the replica (results/) and the production study's anonymised per-fact
verdicts (production/facts.jsonl). Writes results/report.json and results/summary.md, and
production/report.json and production/summary.md.
"""

from __future__ import annotations

import json
import random
import statistics
from collections.abc import Callable
from pathlib import Path
from typing import Any

import arms
import checks
from common import HERE, RESULTS

ERROR_TYPES = ("natural", "number_swap", "invented", "other_offering")
BOOTSTRAP = 2000
Row = dict[str, Any]
Check = Callable[[Row], bool]


def replica_rows() -> list[Row]:
    """One row per judged fact, with every arm's raw verdict."""
    facts = json.loads(arms.FACTS.read_text())
    runs = {name: arms.load(name) for name in arms.ARMS}
    rows = []
    for f in facts:
        if f["raw_status"] != "observed":
            continue
        verdicts = {
            name: data.get(f["source_id"], {}).get("verdicts", {}).get(f["id"])
            for name, data in runs.items()
            if data
        }
        verdicts["A1"] = checks.a1_supported(f)
        verdicts["A1f"] = checks.a1_free_supported(f)
        rows.append(
            {
                "id": f["id"],
                "source": f["source_id"],
                "kind": f["kind"],
                "field": f["field"],
                "label": f["label"],
                "error_type": f["error_type"],
                "base": f["base_status"] == "observed",
                "arms": verdicts,
            }
        )
    return rows


def _prob(name: str, threshold: float) -> Check:
    return lambda r: r["base"] and not ((s := r["arms"].get(name)) is not None and s < threshold)


def _yes_no(name: str) -> Check:
    return lambda r: r["base"] and r["arms"].get(name) is not False


def _flag(name: str) -> Check:
    return lambda r: r["base"] and r["arms"][name]


def _both(a: Check, b: Check) -> Check:
    return lambda r: a(r) and b(r)


def replica_variants(rows: list[Row]) -> dict[str, Check]:
    present = {name for r in rows for name in r["arms"]}
    v: dict[str, Check] = {
        "Baseline (quote check)": lambda r: r["base"],
        "A1 numeric": _flag("A1"),
        'A1 numeric, reading "free" as 0': _flag("A1f"),
    }
    for run in ("B_1", "B_2"):
        if run in present:
            for t in (0.3, 0.5, 0.7):
                v[f"B Jev, whole source @{t}, run {run[-1]}"] = _prob(run, t)
    labels = {
        "C": "C DeepSeek judge, whole source",
        "D": "D gpt-oss-safeguard, cited excerpt only",
        "Dw": "Dw gpt-oss-safeguard, whole source",
    }
    for arm, text in labels.items():
        for n in ("1", "2"):
            if f"{arm}_{n}" in present:
                v[f"{text}, run {n}"] = _yes_no(f"{arm}_{n}")
    for name, a1, arm, check in (
        ("A1 + B Jev @0.5, run 1", "A1", "B_1", _prob("B_1", 0.5)),
        ('A1 ("free" as 0) + B Jev @0.5, run 1', "A1f", "B_1", _prob("B_1", 0.5)),
        ("A1 + C, run 1", "A1", "C_1", _yes_no("C_1")),
        ("A1 + D, run 1", "A1", "D_1", _yes_no("D_1")),
        ("A1 + Dw, run 1", "A1", "Dw_1", _yes_no("Dw_1")),
    ):
        if arm in present:
            v[name] = _both(_flag(a1), check)
    return v


def production_variants() -> dict[str, Check]:
    return {
        "Baseline (quote check)": lambda r: r["base"],
        "A1 numeric": _flag("A1"),
        "A1+2 numeric + OCR": _flag("A12"),
        "B Jev @0.3, batch run 1": _prob("B_batch_1", 0.3),
        "B Jev @0.5, batch run 1": _prob("B_batch_1", 0.5),
        "B Jev @0.5, batch run 2": _prob("B_batch_2", 0.5),
        "B Jev @0.7, batch run 1": _prob("B_batch_1", 0.7),
        "B Jev @0.5, one question per request": _prob("B_single_1", 0.5),
        "C DeepSeek judge, run 1": _yes_no("C_1"),
        "C DeepSeek judge, run 2": _yes_no("C_2"),
        "D gpt-oss-safeguard (excerpt only), run 1": _yes_no("D_1"),
        "D gpt-oss-safeguard (excerpt only), run 2": _yes_no("D_2"),
        "A1 + B Jev @0.5, run 1": _both(_flag("A1"), _prob("B_batch_1", 0.5)),
        "A1+2 + B Jev @0.5, run 1": _both(_flag("A12"), _prob("B_batch_1", 0.5)),
        "A1 + C, run 1": _both(_flag("A1"), _yes_no("C_1")),
        "A1+2 + C, run 1": _both(_flag("A12"), _yes_no("C_1")),
    }


def rates(rows: list[Row], supported: Check) -> dict[str, Any]:
    """Production's metrics, plus the share of each error type caught."""
    wrong = [r for r in rows if r["label"] is False]
    right = [r for r in rows if r["label"] is True]
    kept_wrong = sum(supported(r) for r in wrong)
    kept_right = sum(supported(r) for r in right)
    kept = kept_wrong + kept_right
    out: dict[str, Any] = {
        "wrong": len(wrong),
        "correct": len(right),
        "false_supported": kept_wrong / len(wrong) if wrong else None,
        "wrongly_downgraded": 1 - kept_right / len(right) if right else None,
        "precision": kept_right / kept if kept else None,
        "recall": kept_right / len(right) if right else None,
    }
    for t in ERROR_TYPES:
        group = [r for r in wrong if r["error_type"] == t]
        out[f"caught_{t}"] = 1 - sum(supported(r) for r in group) / len(group) if group else None
        out[f"n_{t}"] = len(group)
    return out


def _counts(rows: list[Row], supported: Check) -> dict[str, int]:
    c = {"wrong": 0, "right": 0, "kept_wrong": 0, "kept_right": 0}
    for r in rows:
        kept = supported(r)
        if r["label"] is True:
            c["right"] += 1
            c["kept_right"] += kept
        else:
            c["wrong"] += 1
            c["kept_wrong"] += kept
            c[f"n_{r['error_type']}"] = c.get(f"n_{r['error_type']}", 0) + 1
            c[f"kept_{r['error_type']}"] = c.get(f"kept_{r['error_type']}", 0) + kept
    return c


def bootstrap(rows: list[Row], supported: Check, seed: int = 11) -> dict[str, list[float]]:
    """95% percentile intervals, resampling whole sources with replacement."""
    by_source: dict[str, list[Row]] = {}
    for r in rows:
        by_source.setdefault(r["source"], []).append(r)
    keys = sorted(by_source)
    counts = [_counts(by_source[k], supported) for k in keys]
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {}
    for _ in range(BOOTSTRAP):
        total: dict[str, int] = {}
        for c in rng.choices(counts, k=len(counts)):
            for key, value in c.items():
                total[key] = total.get(key, 0) + value
        wrong, right = total["wrong"], total["right"]
        kw, kr = total["kept_wrong"], total["kept_right"]
        values = {
            "false_supported": kw / wrong if wrong else None,
            "wrongly_downgraded": 1 - kr / right if right else None,
            "precision": kr / (kw + kr) if kw + kr else None,
            "recall": kr / right if right else None,
        }
        for e in ERROR_TYPES:
            if total.get(f"n_{e}"):
                values[f"caught_{e}"] = 1 - total[f"kept_{e}"] / total[f"n_{e}"]
        for key, value in values.items():
            if value is not None:
                samples.setdefault(key, []).append(value)
    out = {}
    for key, values in samples.items():
        values.sort()
        out[key] = [values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]]
    return out


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def _cell(point: float | None, ci: list[float] | None) -> str:
    if point is None:
        return "n/a"
    return _pct(point) + (f" ({100 * ci[0]:.1f}–{100 * ci[1]:.1f})" if ci else "")


def agreement(rows: list[Row], first: str, second: str, threshold: float | None) -> Any:
    def norm(v: Any) -> Any:
        return None if v is None or threshold is None else v >= threshold

    pairs = [
        (r["arms"].get(first), r["arms"].get(second))
        for r in rows
        if first in r["arms"] and second in r["arms"]
    ]
    if threshold is not None:
        pairs = [(norm(a), norm(b)) for a, b in pairs]
    if not pairs:
        return None
    return {"facts": len(pairs), "same": sum(a == b for a, b in pairs)}


def table(rows: list[Row], variants: dict[str, Check], kinds: list[str]) -> tuple[dict, list[str]]:
    universe = [r for r in rows if r["label"] is not None]
    out: dict[str, Any] = {}
    present = [t for t in ERROR_TYPES if any(r["error_type"] == t for r in universe)]
    lines = [
        f"Universe: {len(universe)} labelled observed facts "
        f"({sum(r['label'] is False for r in universe)} wrong: "
        + ", ".join(f"{t} {sum(r['error_type'] == t for r in universe)}" for t in present)
        + f"; {sum(r['label'] is True for r in universe)} correct) "
        f"from {len({r['source'] for r in universe})} sources. "
        "Brackets: 95% bootstrap interval over sources.",
        "",
        "| Arm | False-supported | Wrongly downgraded | Precision | Recall | "
        + " | ".join(f"Caught: {t}" for t in present)
        + " |",
        "|---|---|---|---|---|" + "---|" * len(present),
    ]
    for name, check in variants.items():
        overall, ci = rates(universe, check), bootstrap(universe, check)
        by_kind = {k: rates([r for r in universe if r["kind"] == k], check) for k in kinds}
        out[name] = {"overall": overall, "ci95": ci, "by_kind": by_kind}
        cells = [
            _cell(overall[m], ci.get(m))
            for m in ("false_supported", "wrongly_downgraded", "precision", "recall")
        ]
        cells += [_cell(overall[f"caught_{t}"], ci.get(f"caught_{t}")) for t in present]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += ["", "False-supported / wrongly downgraded by source kind:", ""]
    lines += ["| Arm | " + " | ".join(kinds) + " |", "|---|" + "---|" * len(kinds)]
    for name, data in out.items():
        cells = [
            f"{_pct(data['by_kind'][k]['false_supported'])} / {_pct(data['by_kind'][k]['wrongly_downgraded'])}"
            for k in kinds
        ]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return out, lines


def _costs(name: str) -> dict[str, Any]:
    data = arms.load(name)
    seconds = sorted(r["seconds"] for r in data.values())
    usd = sum(r["cost_usd"] for r in data.values())
    facts = sum(len(r["verdicts"]) for r in data.values())
    models: dict[str, int] = {}
    for r in data.values():
        for m in r.get("models", []):
            models[m] = models.get(m, 0) + 1
    return {
        "sources": len(data),
        "facts": facts,
        "usd": usd,
        "usd_per_source": usd / len(data),
        "usd_per_1000_facts": 1000 * usd / max(1, facts),
        "p50_seconds": statistics.median(seconds),
        "p95_seconds": seconds[min(len(seconds) - 1, int(0.95 * len(seconds)))],
        "errors": sum(len(r.get("errors", [])) for r in data.values()),
        "unsure": sum(v is None for r in data.values() for v in r["verdicts"].values()),
        "calls": sum(r.get("calls", 1) for r in data.values()),
        "models": models,
    }


def _write(folder: Path, out: dict[str, Any], lines: list[str]) -> None:
    (folder / "report.json").write_text(json.dumps(out, indent=1))
    (folder / "summary.md").write_text("\n".join(lines) + "\n")


def report() -> None:
    rows = replica_rows()
    kinds = ["See", "Do", "Sleep"]
    out, lines = table(rows, replica_variants(rows), kinds)
    result: dict[str, Any] = {"variants": out, "costs": {}, "agreement": {}}
    lines += [
        "",
        "| Run | Sources | USD | USD/source | USD/1k facts | p50 s/source | p95 s/source | Notes |",
    ]
    lines += ["|---|---|---|---|---|---|---|---|"]
    for name in arms.ARMS:
        if not arms.load(name):
            continue
        c = result["costs"][name] = _costs(name)
        lines.append(
            f"| {name} | {c['sources']} | {c['usd']:.4f} | {c['usd_per_source']:.5f} | "
            f"{c['usd_per_1000_facts']:.4f} | {c['p50_seconds']:.1f} | {c['p95_seconds']:.1f} | "
            f"calls {c['calls']}, unsure {c['unsure']}, errors {c['errors']}, models {c['models']} |"
        )
    extractions = json.loads((RESULTS / "extractions.json").read_text())
    result["extraction"] = {
        "sources": len(extractions),
        "usd": sum(e["cost_usd"] for e in extractions.values()),
        "p50_seconds": statistics.median(e["seconds"] for e in extractions.values()),
        "models": sorted({e["model"] for e in extractions.values()}),
        "errors": sum(bool(e["error"]) for e in extractions.values()),
        "truncated": sum(e["truncated"] for e in extractions.values()),
    }
    lines += ["", "Run-to-run agreement on per-fact verdicts (all judged facts):", ""]
    for first, second, t in (
        ("B_1", "B_2", 0.5),
        ("C_1", "C_2", None),
        ("D_1", "D_2", None),
        ("Dw_1", "Dw_2", None),
    ):
        a = agreement(rows, first, second, t)
        if a:
            result["agreement"][f"{first} vs {second}"] = a
            lines.append(
                f"- {first} vs {second}: {a['same']} of {a['facts']} ({_pct(a['same'] / a['facts'])})"
            )
    lines += [
        "",
        "Jev probability calibration (B_1; share of labelled facts in bucket that are correct):",
        "",
    ]
    scored = [(r["arms"].get("B_1"), r["label"]) for r in rows if r["label"] is not None]
    for low, high in ((0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)):
        bucket = [ok for v, ok in scored if v is not None and low <= v < high]
        lines.append(
            f"- {low:.1f}–{min(high, 1):.1f}: {len(bucket)} facts, {_pct(sum(bucket) / len(bucket) if bucket else None)} correct"
        )
    _write(RESULTS, result, lines)
    print("\n".join(lines))
    production = HERE / "production" / "facts.jsonl"
    if production.exists():
        prod_rows = [json.loads(line) for line in production.read_text().splitlines() if line]
        out, lines = table(
            prod_rows, production_variants(), ["text", "csv", "pdf", "image", "website"]
        )
        result = {"variants": out, "agreement": {}}
        lines += ["", "Run-to-run agreement on per-fact verdicts:", ""]
        for first, second, t in (
            ("B_batch_1", "B_batch_2", 0.5),
            ("B_batch_1", "B_single_1", 0.5),
            ("C_1", "C_2", None),
            ("D_1", "D_2", None),
        ):
            a = agreement(prod_rows, first, second, t)
            result["agreement"][f"{first} vs {second}"] = a
            lines.append(
                f"- {first} vs {second}: {a['same']} of {a['facts']} ({_pct(a['same'] / a['facts'])})"
            )
        _write(HERE / "production", result, lines)
        print("\n".join(lines))
