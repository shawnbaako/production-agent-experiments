"""Extract once, label and inject errors, judge with every arm, score.

    OPENROUTER_API_KEY=... uv run python run.py extract
    uv run python run.py facts
    OPENROUTER_API_KEY=... uv run python run.py arms [B_1 C_1 ...]
    uv run python run.py report                       # no network; from recorded results

Every stage records its output under results/ and skips work already recorded, so a rerun
never repeats a model call. All arms judge the same recorded facts.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic import ValidationError

import arms
import labels
import report
from common import (
    EXTRACT_MODEL,
    RESULTS,
    BusinessSuggestion,
    ProposedOffering,
    _Fact,
    chat,
    sources,
    spent,
    system_prompt,
    user_prompt,
)

EXTRACTIONS = RESULTS / "extractions.json"


def _lenient(
    model: type[ProposedOffering] | type[BusinessSuggestion], data: Any
) -> dict[str, Any] | None:
    """Production tolerance: one malformed fact becomes unknown, not a lost proposal."""
    if not isinstance(data, dict):
        return None
    clean = dict(data)
    for name, info in model.model_fields.items():
        kind = info.annotation
        if name in clean and isinstance(kind, type) and issubclass(kind, _Fact):
            try:
                kind.model_validate(clean[name])
            except ValidationError:
                clean[name] = {"status": "unknown"}
    try:
        return model.model_validate(clean).model_dump()
    except ValidationError:
        return None


def salvage(text: str) -> dict[str, Any]:
    """Production's salvage: keep each fully closed offering from output cut at the budget."""
    start = text.find("[", text.find('"offerings"'))
    if start < 0:
        return {}
    decoder = json.JSONDecoder()
    offerings: list[Any] = []
    position = start + 1
    while True:
        while position < len(text) and text[position] in " \n\r\t,":
            position += 1
        if position >= len(text) or text[position] != "{":
            break
        try:
            item, position = decoder.raw_decode(text, position)
        except json.JSONDecodeError:
            break
        offerings.append(item)
    return {"offerings": offerings, "truncated": True}


def _parse(text: str) -> dict[str, Any]:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return salvage(text)
    return raw if isinstance(raw, dict) else {}


def _extract_one(source: dict[str, Any], system: str) -> dict[str, Any]:
    result = chat("extract", EXTRACT_MODEL, system, user_prompt(source), json_mode=True)
    raw = _parse(result.text)
    offerings = [
        o for o in (_lenient(ProposedOffering, x) for x in raw.get("offerings") or []) if o
    ]
    business = _lenient(BusinessSuggestion, raw.get("business")) if raw.get("business") else None
    print(source["id"], len(offerings), "offerings", f"${result.cost_usd:.5f}", result.error or "")
    return {
        "model": result.model,
        "provider": result.provider,
        "cost_usd": result.cost_usd,
        "seconds": round(result.seconds, 2),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "error": result.error,
        "parsed": bool(raw),
        "offerings": offerings,
        "business": business,
        "notes": raw.get("notes"),
        "truncated": bool(raw.get("truncated")),
        "raw_text": result.text if raw.get("truncated") or not raw else None,
    }


def extract(limit: int | None = None) -> None:
    done = json.loads(EXTRACTIONS.read_text()) if EXTRACTIONS.exists() else {}
    system = system_prompt()
    todo = [s for s in sources()[:limit] if s["id"] not in done or done[s["id"]]["error"]]
    with ThreadPoolExecutor(6) as pool:
        for source, result in zip(
            todo, pool.map(lambda s: _extract_one(s, system), todo), strict=False
        ):
            done[source["id"]] = result
            EXTRACTIONS.write_text(json.dumps(done, indent=1, ensure_ascii=False))


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    stage = sys.argv[1] if len(sys.argv) > 1 else "report"
    rest = sys.argv[2:]
    limit = int(rest.pop(0)[len("--limit=") :]) if rest and rest[0].startswith("--limit=") else None
    if stage == "extract":
        extract(limit)
    elif stage == "facts":
        labels.build_facts()
    elif stage == "arms":
        arms.run_all(set(rest) or None, limit)
    elif stage == "report":
        report.report()
    else:
        sys.exit(__doc__)
    print(f"OpenRouter spend recorded: ${spent():.4f}")


if __name__ == "__main__":
    main()
