"""Label the extracted facts against the listings, then inject wrong facts.

Ground truth is the listing templates of each Wikivoyage section: name, address, hours, price
and description of every business. A natural fact is labelled correct when its value is in
the listing it belongs to, by field-specific rules below; a natural fact the rules cannot
confirm is left out of the scored set (no person reviewed every one, so these are not reported
as extractor errors). The hand check in results/hand_check.json measures how often these
labels are right.

Wrong facts are injected with the production study's seed, taxonomy and code: one swapped
digit or unit, one invented fact carrying an unrelated real line as its excerpt, and one
value taken from another offering in the same source, per source where possible. One guard
is added for public data: a value moved from another offering is skipped when the target
listing states that same value too, because then the moved fact is true.
"""

from __future__ import annotations

import json
import random
import re
from typing import Any

from rapidfuzz import fuzz

import checks
from common import BUSINESS_FIELDS, OFFER_FIELDS, RESULTS, baseline_status, numbers, sources
from fetch import render

FACTS = RESULTS / "facts.json"
SEED = 20261101
NUMERIC = ("price_minor", "duration_minutes", "capacity", "minimum_age")
INVENTED = {
    "minimum_age": 12,
    "capacity": 15,
    "duration_minutes": 120,
    "cancellation_wording": "Full refund up to 24 hours before the start time",
    "requirements": ["Valid photo ID"],
    "languages": ["English", "French"],
    "includes": ["hotel pick-up"],
}
# A listing "states" one of the invented fields when its text mentions the field at all, so
# an invented value is only ever placed where the listing says nothing about that field.
MENTIONS = {
    "minimum_age": r"\bage[sd]?\b|years? old|\d+\s?\+|\bminimum\b|\bunder \d|\bover \d|adults? only|\bkids?\b|child",
    "capacity": r"\bup to\b|\bmax|capacity|group size|\bseats?\b|\bpeople\b|\bguests?\b|passengers|\bpersons?\b|\bsleeps\b",
    "duration_minutes": r"\bhours?\b|\bhrs?\b|\bminutes?\b|\bmins?\b|\bdays?\b|\d\s?h\b|half[- ]day|full[- ]day",
    "cancellation_wording": r"cancel|refund",
    "requirements": r"\bID\b|identification|passport|\bmust\b|requir|\bneed",
    "languages": r"english|french|spanish|german|japanese|chinese|language|bilingual",
    "includes": r"includ|pick-?up|transport|shuttle",
}
DOLLARS = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?")
KINDS = {
    "sleep": ["stay", "rental"],
    "see": ["experience", "other"],
    "do": ["experience", "rental", "other"],
    "go": ["experience", "rental", "other"],
    **dict.fromkeys(("eat", "drink", "buy"), ["experience", "other"]),
}
FREE = re.compile(r"\bfree\b", re.I)
PER_PERSON = re.compile(
    r"per (person|adult|child|head)|/\s?(person|adult)|\badults?\b|\beach\b|\bpp\b|admission", re.I
)
PER_UNIT = re.compile(r"per (car|vehicle|boat|group|family|room|night|site|cabin)|/\s?night", re.I)


def _plain(text: Any) -> str:
    text = ", ".join(text) if isinstance(text, list) else str(text or "")
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text.lower()).split())


def _tokens(text: Any) -> set[str]:
    return set(_plain(text).split())


def _same_text(value: Any, truth: Any) -> bool:
    a, b = _plain(value), _plain(truth)
    return bool(a and b) and (a in b or b in a or fuzz.token_set_ratio(a, b) >= 80)


def _wording(field: str, value: Any, truth: str) -> bool:
    """Production's wording rule: no number the truth lacks, and 40% of words shared."""
    extra = set(numbers(_plain(value))) - set(numbers(_plain(truth)))
    overlap = len(_tokens(value) & _tokens(truth)) / max(1, len(_tokens(value)))
    return overlap >= 0.4 if field == "schedule_wording" else not extra and overlap >= 0.4


def stated_cents(item: dict[str, str]) -> set[int]:
    text = f"{item.get('price', '')} {item.get('content', '')}"
    return {
        int(whole.replace(",", "")) * 100 + (int(cents.ljust(2, "0")) if cents else 0)
        for whole, cents in DOLLARS.findall(text)
    }


def _body(item: dict[str, str]) -> str:
    """The listing's words other than its address, phone and opening hours."""
    return " ".join(item.get(k, "") for k in ("price", "content", "checkin", "checkout"))


def label(field: str, value: Any, item: dict[str, str], source: dict[str, Any]) -> tuple[bool, str]:
    """(correct, reason) for one natural fact against the listing it was matched to."""
    text = render(item)
    if field == "title":
        names = [item.get("name"), item.get("alt")]
        a = _plain(value)
        ok = any(n and (a == _plain(n) or a in _plain(n) or _plain(n) in a) for n in names)
        return ok, f"listing name {item.get('name')!r}"
    if field == "kind":
        accepted = KINDS.get(item.get("type", ""), [])
        return value in accepted, f"listing type {item.get('type')}"
    if field == "description":
        tokens = _tokens(value)
        inside = len(tokens & _tokens(text)) / max(1, len(tokens))
        return inside >= 0.8, f"{inside:.0%} of description words are in the listing"
    if field == "location":
        places = [item.get("address"), item.get("directions"), source["city"]]
        ok = any(_same_text(value, p) for p in places if p) or _plain(value) in _plain(text)
        return ok, "address, directions or city" if ok else "place not in the listing"
    if field == "price_minor":
        if int(value) == 0:
            return bool(FREE.search(item.get("price", ""))), "listing price says free"
        return int(value) in stated_cents(item), f"listing amounts {sorted(stated_cents(item))}"
    if field == "price_basis":
        accepted = ["per_unit", "per_commitment"] if item.get("type") == "sleep" else []
        if PER_PERSON.search(_body(item)):
            accepted += ["per_person", "per_seat"]
        if PER_UNIT.search(_body(item)):
            accepted += ["per_unit", "per_commitment"]
        return value in accepted, f"basis words allow {sorted(set(accepted))}"
    if field in {"includes", "requirements", "languages"}:
        missing = [v for v in value if fuzz.partial_ratio(_plain(v), _plain(text)) < 85]
        return not missing, f"not in listing: {missing}" if missing else "all items in listing"
    if field == "duration_minutes":
        return int(value) in checks._minutes(_body(item)), "length stated in the listing"
    if field in {"capacity", "minimum_age"}:
        return int(value) in checks._integers(_body(item)), "number stated in the listing"
    if field in {"price_wording", "cancellation_wording", "schedule_wording"}:
        return _wording(field, value, text), "wording rule against the listing"
    raise ValueError(field)


def _match(title: str, items: list[dict[str, str]]) -> int | None:
    """Production's title match: token-set ratio of at least 70 against the listing name."""
    scored = [
        (fuzz.token_set_ratio(_plain(title), _plain(t.get("name"))), i) for i, t in enumerate(items)
    ]
    best = max(scored, default=(0, None))
    return best[1] if best[0] >= 70 else None


def _truth_facts(item: dict[str, str], natural: list[dict[str, Any]]) -> dict[str, Any]:
    """What a listing states, in the shape production's injection reads (field -> value)."""
    text = render(item)
    facts: dict[str, Any] = {}
    for field, pattern in MENTIONS.items():
        if re.search(pattern, text, re.I):
            facts[field] = "stated"
    for record in natural:
        if record["label"] or record["raw_status"] != "observed":
            facts[record["field"]] = record["value"] if record["label"] else "stated"
    return facts


def _record(
    source: dict[str, Any], key: str, field: str, fact: dict[str, Any], **extra: Any
) -> dict[str, Any]:
    return {
        "id": f"{source['id']}:{key}:{field}",
        "source_id": source["id"],
        "kind": source["section"],
        "field": field,
        "value": fact.get("value"),
        "excerpt": fact.get("excerpt"),
        "raw_status": fact["status"],
        "base_status": baseline_status(fact["status"], fact.get("excerpt"), source["text"]),
        **extra,
    }


def build_facts() -> None:
    extractions = json.loads((RESULTS / "extractions.json").read_text())
    rng = random.Random(SEED)
    facts: list[dict[str, Any]] = []
    for source in sources():
        extraction = extractions.get(source["id"])
        if extraction is None:
            continue
        items = source["listings"]
        natural: list[dict[str, Any]] = []
        for index, offering in enumerate(extraction["offerings"]):
            title = (offering.get("title") or {}).get("value") or ""
            match = _match(title, items)
            for field in OFFER_FIELDS:
                fact = offering.get(field) or {}
                if fact.get("status") in (None, "unknown", "contradictory") or fact.get(
                    "value"
                ) in (None, "", []):
                    continue
                record = _record(
                    source, f"o{index}", field, fact, offering=title, truth_offering=match
                )
                if match is None:
                    record["label"], record["label_reason"] = None, "offering matches no listing"
                else:
                    ok, reason = label(field, fact["value"], items[match], source)
                    # A fact the rules cannot confirm is left out, not counted as an error.
                    record["label"], record["label_reason"] = (True if ok else None), reason
                record["error_type"] = None
                natural.append(record)
        for field in BUSINESS_FIELDS:
            fact = (extraction.get("business") or {}).get(field) or {}
            if fact.get("status") in (None, "unknown", "contradictory") or not fact.get("value"):
                continue
            # A guide section lists many businesses; there is no single operator to label.
            natural.append(
                _record(source, "biz", field, fact, offering="(business)", truth_offering=None)
                | {"label": None, "label_reason": "no single operator", "error_type": None}
            )
        truth = {
            "offerings": [
                {
                    "title": item.get("name"),
                    "facts": _truth_facts(item, [r for r in natural if r["truth_offering"] == i]),
                }
                for i, item in enumerate(items)
            ]
        }
        facts += natural + _inject(rng, source, natural, truth)
    FACTS.write_text(json.dumps(facts, indent=1, ensure_ascii=False))
    scored = [f for f in facts if f["raw_status"] == "observed" and f["label"] is not None]
    print(
        f"facts {len(facts)}; observed+labelled {len(scored)}; "
        f"correct {sum(f['label'] is True for f in scored)}; "
        f"injected {sum(f['error_type'] is not None for f in facts)}; "
        f"natural left out {sum(f['label'] is None and f['raw_status'] == 'observed' for f in facts)}"
    )


def _holds_for(item: dict[str, str], fact: dict[str, Any]) -> bool:
    """Whether a value moved from another offering is also true of the target listing."""
    text = render(item)
    if fact["field"] in NUMERIC or fact["field"] == "cancellation_wording":
        if fact["field"] == "price_minor":
            return int(fact["value"]) in stated_cents(item)
        return checks.numeric_supported(fact["field"], fact["value"], _body(item)) is not False
    if fact["field"] == "includes":
        return all(fuzz.partial_ratio(_plain(v), _plain(text)) >= 85 for v in fact["value"])
    return _wording(fact["field"], fact["value"], text)


def _inject(
    rng: random.Random, source: dict[str, Any], natural: list[dict[str, Any]], truth: dict
) -> list[dict[str, Any]]:
    """Production's injection, unchanged apart from the _holds_for guard."""
    good = [
        f
        for f in natural
        if f["label"] and f["raw_status"] == "observed" and f["truth_offering"] is not None
    ]
    out: list[dict[str, Any]] = []
    source_text = source["text"]

    def add(
        base: dict[str, Any], kind: str, field: str, value: Any, excerpt: str, note: str
    ) -> None:
        fact = {"status": "observed", "value": value, "excerpt": excerpt}
        record = _record(
            source,
            f"inj{len(out)}",
            field,
            fact,
            offering=base["offering"],
            truth_offering=base["truth_offering"],
            error_type=kind,
        )
        record.update(label=False, label_reason=note)
        out.append(record)

    numeric = [f for f in good if f["field"] in NUMERIC]
    if numeric:
        base = rng.choice(numeric)
        value = int(base["value"])
        digits = str(value // 100 if base["field"] == "price_minor" else value)
        if len(set(digits)) > 1:
            i = rng.randrange(len(digits) - 1)
            while digits[i] == digits[i + 1]:
                i = (i + 1) % (len(digits) - 1)
            swapped = int(digits[:i] + digits[i + 1] + digits[i] + digits[i + 2 :])
            new = swapped * 100 if base["field"] == "price_minor" else swapped
            note = "swapped digits"
        elif base["field"] == "duration_minutes" and value % 60 == 0:
            new, note = value // 60, "hours recorded as minutes"
        else:
            new, note = value * 10, "unit/scale error (x10)"
        if new != value:
            add(
                base,
                "number_swap",
                base["field"],
                new,
                base["excerpt"],
                f"{note}: {value} -> {new}",
            )
    if good:
        base = rng.choice(good)
        gt = truth["offerings"][base["truth_offering"]]["facts"]
        candidates = [f for f in INVENTED if gt.get(f) in (None, [])]
        lines = [line.strip() for line in source_text.splitlines() if len(line.strip()) > 25]
        if candidates and lines:
            field = rng.choice(candidates)
            add(
                base,
                "invented",
                field,
                INVENTED[field],
                rng.choice(lines)[:200],
                f"invented {field}; excerpt is an unrelated real line",
            )
    by_offer: dict[int, list[dict[str, Any]]] = {}
    for f in good:
        by_offer.setdefault(f["truth_offering"], []).append(f)
    if len(by_offer) >= 2:
        target, donor = rng.sample(sorted(by_offer), 2)
        gt_target = truth["offerings"][target]["facts"]
        gt_donor = truth["offerings"][donor]["facts"]
        donated = [
            f
            for f in by_offer[donor]
            if f["field"] in (*NUMERIC, "cancellation_wording", "schedule_wording", "includes")
            and gt_target.get(f["field"]) != gt_donor.get(f["field"])
            and not _holds_for(source["listings"][target], f)
        ]
        if donated:
            fact = rng.choice(donated)
            base = by_offer[target][0]
            add(
                base,
                "other_offering",
                fact["field"],
                fact["value"],
                fact["excerpt"] or "",
                f"{fact['field']} of '{fact['offering']}' assigned to '{base['offering']}'",
            )
    return out
