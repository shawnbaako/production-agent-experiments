"""Arm A: the deterministic number and unit check, copied from the production study.

A fact whose field carries a number (price, duration, capacity, minimum age, cancellation
hours or percent) is downgraded when that number is not stated in the fact's own excerpt.
It can only move an ``observed`` fact to ``inferred``. The production study's OCR quote
check (A2) and entailment check (A3) are not part of this replica: there are no photos
here, and A3 was not recommended.

    uv run python checks.py     # self-check of the parsers
"""

from __future__ import annotations

import re
from typing import Any

NUMERIC_FIELDS = frozenset(
    {"price_minor", "duration_minutes", "capacity", "minimum_age", "cancellation_wording"}
)

_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "forty-eight": 48,
    "fifty": 50,
    "sixty": 60,
    "ninety": 90,
}
_NUMBER = r"(\d+(?:\.\d+)?(?:½)?|½|" + "|".join(sorted(_WORDS, key=lambda word: -len(word))) + r")"
_UNIT = re.compile(
    _NUMBER + r"(?:\s+and\s+a\s+half)?\s*-?\s*(hours?|hrs?|h|minutes?|mins?|min|m|days?)\b",
    re.IGNORECASE,
)
_RANGE = re.compile(
    r"(\d{1,2})(?::(\d{2}))?\s*([ap])?\.?m?\.?\s*(?:-|–|to)\s*(\d{1,2})(?::(\d{2}))?\s*([ap])?",
    re.IGNORECASE,
)


def _num(token: str) -> float:
    token = token.lower()
    if token in _WORDS:
        return float(_WORDS[token])
    if token == "½":
        return 0.5
    if token.endswith("½"):
        return float(token[:-1]) + 0.5
    return float(token)


def _integers(text: str) -> set[int]:
    found = {int(n.replace(",", "")) for n in re.findall(r"\d{1,3}(?:,\d{3})+|\d+", text)}
    found |= {value for word, value in _WORDS.items() if re.search(rf"\b{word}\b", text, re.I)}
    return found


def _cents(text: str) -> set[int]:
    out = set()
    for whole, decimals in re.findall(r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?", text):
        out.add(
            int(whole.replace(",", "")) * 100 + (int(decimals.ljust(2, "0")) if decimals else 0)
        )
    return out


def _minutes(text: str) -> set[int]:
    """Every duration in minutes the excerpt states, including '1 hour 30 minutes' sums."""
    spans: list[tuple[int, int, float]] = []
    for match in _UNIT.finditer(text):
        amount = _num(match.group(1)) + (0.5 if "half" in match.group(0).lower() else 0)
        unit = match.group(2).lower()
        factor = 1440 if unit.startswith("d") else 1 if unit.startswith("m") else 60
        spans.append((match.start(), match.end(), amount * factor))
    found = {round(minutes) for _, _, minutes in spans}
    for (_, end, first), (start, _, second) in zip(spans, spans[1:], strict=False):
        if start - end <= 6:
            found.add(round(first + second))
    for compact in re.finditer(r"(\d+)\s*h\s*(\d{2})\b", text, re.I):
        found.add(int(compact.group(1)) * 60 + int(compact.group(2)))
    for match in _RANGE.finditer(text):
        h1, m1, p1, h2, m2, p2 = match.groups()
        start = (
            int(h1) % 12 * 60
            + int(m1 or 0)
            + (720 if (p1 or p2 or "").lower() == "p" and p1 else 0)
        )
        end = int(h2) % 12 * 60 + int(m2 or 0) + (720 if (p2 or "").lower() == "p" else 0)
        if int(h2) > 12 or int(h1) > 12:
            start, end = int(h1) * 60 + int(m1 or 0), int(h2) * 60 + int(m2 or 0)
        if end > start:
            found.add(end - start)
    found |= _integers(text) if not spans else set()
    return found


def numeric_supported(field: str, value: Any, excerpt: str | None) -> bool | None:
    """Whether the excerpt states the fact's number; None when the field has no number."""
    if field not in NUMERIC_FIELDS or value in (None, "", []):
        return None
    text = excerpt or ""
    if field == "price_minor":
        return int(value) in _cents(text)
    if field == "duration_minutes":
        return int(value) in _minutes(text)
    if field in {"capacity", "minimum_age"}:
        return int(value) in _integers(text)
    stated = _integers(text)
    stated |= {n * 24 for n in stated}
    return all(n in stated or n * 100 in _cents(text) for n in _integers(str(value)))


def a1_supported(fact: dict[str, Any]) -> bool:
    """Arm A1 on one fact: False only when the number is missing from its excerpt."""
    return numeric_supported(fact["field"], fact["value"], fact.get("excerpt")) is not False


_FREE = re.compile(r"\bfree\b|\bno charge\b|\bcomplimentary\b", re.IGNORECASE)


def a1_free_supported(fact: dict[str, Any]) -> bool:
    """A1 with the fix production made later: "free" in the excerpt states a price of 0."""
    if fact["field"] == "price_minor" and fact["value"] == 0:
        return bool(_FREE.search(fact.get("excerpt") or ""))
    return a1_supported(fact)


if __name__ == "__main__":
    assert numeric_supported("price_minor", 6500, "$65 per adult, $40 for kids") is True
    assert numeric_supported("price_minor", 5600, "$65 per adult") is False
    assert numeric_supported("duration_minutes", 150, "About 2.5 hours on the water") is True
    assert numeric_supported("duration_minutes", 150, "Two and a half hours") is True
    assert numeric_supported("duration_minutes", 90, "1 hour 30 minutes") is True
    assert numeric_supported("duration_minutes", 150, "9:00am-11:30am") is True
    assert numeric_supported("duration_minutes", 2, "2 hours") is False
    assert numeric_supported("capacity", 8, "2-8 players") is True
    assert (
        numeric_supported("cancellation_wording", "48 hours, full refund", "Cancel 2 days ahead")
        is True
    )
    assert a1_free_supported({"field": "price_minor", "value": 0, "excerpt": "Free."})
    assert not a1_supported({"field": "price_minor", "value": 0, "excerpt": "Free."})
    print("ok")
