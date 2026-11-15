"""Build the public sources: listing sections of English Wikivoyage articles (CC BY-SA 4.0).

One source is one "See", "Do" or "Sleep" section of one US destination article: several
businesses with their prices, hours, addresses and descriptions, so a fact can be taken from
the wrong offering. Every listing template is kept as structured data (the ground truth) and
rendered to plain text the way the page shows it (what the extractor reads).

    uv run python fetch.py            # writes data/sources.json (skips if present)

Standard library only. Each source records the page title, revision id and licence.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "sources.json"
INDEX = "https://en.wikivoyage.org/w/index.php"
UA = "production-agent-experiments/1.0 (research script)"
SECTIONS = ("See", "Do", "Sleep")
LISTING = {"see", "do", "sleep", "eat", "drink", "buy", "go", "listing"}
MAX_SOURCES = 130
PER_PAGE = 3

# US destinations with tours, attractions and lodging, priced in US dollars.
DESTINATIONS = [
    ("Ketchikan", "AK"), ("Juneau", "AK"), ("Skagway", "AK"), ("Sitka", "AK"), ("Seward", "AK"),
    ("Homer", "AK"), ("Key West", "FL"), ("St. Augustine", "FL"), ("Islamorada", "FL"),
    ("Sanibel Island", "FL"), ("Savannah", "GA"), ("Tybee Island", "GA"), ("Charleston (South Carolina)", "SC"),
    ("Hilton Head Island", "SC"), ("Myrtle Beach", "SC"), ("Asheville", "NC"), ("Outer Banks", "NC"),
    ("Gatlinburg", "TN"), ("Branson", "MO"), ("Eureka Springs", "AR"), ("Hot Springs (Arkansas)", "AR"),
    ("Natchez", "MS"), ("Galveston", "TX"), ("Fredericksburg (Texas)", "TX"), ("South Padre Island", "TX"),
    ("Marfa", "TX"), ("Sedona", "AZ"), ("Flagstaff", "AZ"), ("Bisbee", "AZ"), ("Tombstone", "AZ"),
    ("Jerome (Arizona)", "AZ"), ("Moab", "UT"), ("Park City", "UT"), ("Santa Fe", "NM"), ("Taos", "NM"),
    ("Durango (Colorado)", "CO"), ("Estes Park", "CO"), ("Telluride", "CO"), ("Ouray", "CO"),
    ("Aspen", "CO"), ("Breckenridge", "CO"), ("Jackson (Wyoming)", "WY"), ("Cody", "WY"),
    ("West Yellowstone", "MT"), ("Whitefish", "MT"), ("Sun Valley", "ID"), ("Deadwood", "SD"),
    ("Bar Harbor", "ME"), ("Kennebunkport", "ME"), ("Provincetown", "MA"), ("Nantucket", "MA"),
    ("Martha's Vineyard", "MA"), ("Mackinac Island", "MI"), ("Door County", "WI"), ("Put-in-Bay", "OH"),
    ("Cape May", "NJ"), ("Ocean City (Maryland)", "MD"), ("Chincoteague", "VA"),
    ("Williamsburg (Virginia)", "VA"), ("Gettysburg", "PA"), ("Lake Placid", "NY"), ("Stowe", "VT"),
    ("Hilo", "HI"), ("Kailua-Kona", "HI"), ("Lahaina", "HI"), ("Kihei", "HI"), ("Hanalei", "HI"),
    ("Monterey", "CA"), ("Carmel-by-the-Sea", "CA"), ("Santa Barbara", "CA"), ("Catalina Island", "CA"),
    ("Mammoth Lakes", "CA"), ("South Lake Tahoe", "CA"), ("Napa", "CA"), ("Mendocino", "CA"),
    ("Solvang", "CA"), ("Astoria (Oregon)", "OR"), ("Bend", "OR"), ("Hood River", "OR"),
    ("Friday Harbor", "WA"), ("Leavenworth (Washington)", "WA"),
    ("Talkeetna", "AK"), ("Valdez", "AK"), ("Haines", "AK"), ("Fairbanks", "AK"), ("Marathon (Florida)", "FL"),
    ("Naples (Florida)", "FL"), ("Amelia Island", "FL"), ("Apalachicola", "FL"), ("Beaufort (South Carolina)", "SC"),
    ("Boone", "NC"), ("Bryson City", "NC"), ("Pigeon Forge", "TN"), ("Chattanooga", "TN"), ("Helen", "GA"),
    ("Dahlonega", "GA"), ("Gulf Shores", "AL"), ("Port Aransas", "TX"), ("Alpine (Texas)", "TX"),
    ("Silverton (Colorado)", "CO"), ("Steamboat Springs", "CO"), ("Pagosa Springs", "CO"), ("Salida", "CO"),
    ("Springdale (Utah)", "UT"), ("Kanab", "UT"), ("Torrey", "UT"), ("Williams (Arizona)", "AZ"),
    ("Prescott", "AZ"), ("Ruidoso", "NM"), ("Red River (New Mexico)", "NM"), ("Big Sky", "MT"),
    ("Red Lodge", "MT"), ("Sandpoint", "ID"), ("McCall", "ID"), ("Hill City (South Dakota)", "SD"),
    ("Grand Marais (Minnesota)", "MN"), ("Ely (Minnesota)", "MN"), ("Bayfield (Wisconsin)", "WI"),
    ("Traverse City", "MI"), ("Saugatuck", "MI"), ("Galena (Illinois)", "IL"), ("Ogunquit", "ME"),
    ("Camden (Maine)", "ME"), ("Block Island", "RI"), ("Newport (Rhode Island)", "RI"), ("Mystic", "CT"),
    ("North Conway", "NH"), ("Rehoboth Beach", "DE"), ("Harpers Ferry", "WV"), ("Luray", "VA"),
    ("Lake George (village)", "NY"), ("Montauk", "NY"), ("Paia", "HI"), ("Kapaa", "HI"), ("Volcano (Hawaii)", "HI"),
    ("Half Moon Bay", "CA"), ("Cambria", "CA"), ("Big Bear Lake", "CA"), ("Julian (California)", "CA"),
    ("Healdsburg", "CA"), ("Cannon Beach", "OR"), ("Newport (Oregon)", "OR"), ("Port Townsend", "WA"),
    ("Winthrop (Washington)", "WA"),
]  # fmt: skip


def _fetch(title: str, **params: str) -> str:
    # The action API rate-limits this client (HTTP 429), so pages are read through index.php.
    query = urllib.parse.urlencode({"title": title, **params})
    request = urllib.request.Request(f"{INDEX}?{query}", headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read().decode()
    time.sleep(1)
    return text


def page(name: str) -> dict[str, Any]:
    """The latest revision of a page, following one redirect: title, revision id, wikitext."""
    title = name
    for _ in range(2):
        history = _fetch(title, action="history", limit="1")
        revid = int(re.search(r'data-mw-revid="(\d+)"', history).group(1))
        stamp = re.search(r'data-mw-ts="(\d+)"', history).group(1)
        text = _fetch(title, action="raw", oldid=str(revid))
        target = re.match(r"#REDIRECT\s*\[\[([^\]|#]+)", text, re.I)
        if not target:
            return {"title": title, "revid": revid, "timestamp": stamp, "wikitext": text}
        title = target.group(1).strip()
    raise RuntimeError(f"double redirect at {name}")


def _templates(text: str) -> list[tuple[int, int]]:
    """(start, end) of every top-level {{...}} in text."""
    spans, depth, start, i = [], 0, 0, 0
    while i < len(text) - 1:
        pair = text[i : i + 2]
        if pair == "{{":
            if depth == 0:
                start = i
            depth += 1
            i += 2
        elif pair == "}}" and depth:
            depth -= 1
            i += 2
            if depth == 0:
                spans.append((start, i))
        else:
            i += 1
    return spans


def _split_params(body: str) -> list[str]:
    parts, depth, current = [], 0, []
    i = 0
    while i < len(body):
        pair = body[i : i + 2]
        if pair in ("{{", "[["):
            depth += 1
            current.append(pair)
            i += 2
            continue
        if pair in ("}}", "]]") and depth:
            depth -= 1
            current.append(pair)
            i += 2
            continue
        if body[i] == "|" and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(body[i])
        i += 1
    parts.append("".join(current))
    return parts


def plain(wikitext: str) -> str:
    """Wiki markup to the text a reader sees."""
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", wikitext, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    for start, end in reversed(_templates(text)):
        params = _split_params(text[start + 2 : end - 2])
        name = params[0].strip().lower()
        if name == "convert" and len(params) >= 3:
            replacement = f"{params[1].strip()} {params[2].strip()}"
        elif name in {"nowrap", "nobr", "small"} and len(params) >= 2:
            replacement = params[1]
        else:
            replacement = ""
        text = text[:start] + replacement + text[end:]
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\]", "", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&ndash;", "–").replace("&amp;", "&")
    return re.sub(r"[ \t]+", " ", text).strip()


def listing(params: list[str]) -> dict[str, str]:
    fields = {}
    for part in params[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            fields[key.strip().lower()] = plain(value)
    template = params[0].strip().lower()
    # {{listing|type=do}} names its kind in a parameter.
    fields["type"] = fields.get("type", template) if template == "listing" else template
    return fields


def render(item: dict[str, str]) -> str:
    """One listing as the page shows it: name, address, phone, hours, price, description."""
    head = item.get("name", "")
    if item.get("alt"):
        head += f" ({item['alt']})"
    if item.get("address"):
        head += f", {item['address']}"
    if item.get("directions"):
        head += f" ({item['directions']})"
    for key, mark in (("phone", "☎ "), ("tollfree", "toll-free: "), ("email", "")):
        if item.get(key):
            head += f", {mark}{item[key]}"
    parts = [head]
    if item.get("checkin") or item.get("checkout"):
        times = [f"Check-in: {item['checkin']}" if item.get("checkin") else ""]
        times.append(f"check-out: {item['checkout']}" if item.get("checkout") else "")
        parts.append(", ".join(t for t in times if t))
    parts += [item[k] for k in ("hours", "price", "content") if item.get(k)]
    return ". ".join(p.strip().rstrip(".") for p in parts if p.strip()) + "."


def sections(wikitext: str) -> dict[str, str]:
    found = {}
    heads = list(re.finditer(r"^==\s*([^=].*?)\s*==\s*$", wikitext, re.M))
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(wikitext)
        found[head.group(1).strip()] = wikitext[head.end() : end]
    return found


def build_section(body: str) -> tuple[str, list[dict[str, str]]]:
    """Rendered text and listings of one section."""
    items: list[dict[str, str]] = []
    out = body
    for start, end in reversed(_templates(body)):
        params = _split_params(body[start + 2 : end - 2])
        if params[0].strip().lower() in LISTING:
            item = listing(params)
            if item.get("name"):
                items.insert(0, item)
                out = out[:start] + f"\x00{len(items)}\x00" + out[end:]
                continue
        out = out[:start] + out[end:]
    # Placeholders were numbered from the end; map them back to document order.
    count = len(items)
    lines = []
    for raw in out.splitlines():
        raw = re.sub(r"^=+\s*(.*?)\s*=+$", r"\1", raw.strip())
        raw = raw.lstrip("*#:; ").strip()

        def put(match: re.Match[str]) -> str:
            return render(items[count - int(match.group(1))])

        line = re.sub(r"\x00(\d+)\x00", put, raw)
        if "\x00" not in raw:
            line = plain(line)
        if line:
            lines.append(line)
    return "\n".join(lines), items


def main() -> None:
    if OUT.exists():
        sys.exit(f"{OUT} exists; delete it to rebuild")
    state = dict(DESTINATIONS)
    sources = []
    for name, _ in DESTINATIONS:
        try:
            revision = page(name)
        except (urllib.error.HTTPError, AttributeError) as error:
            print("missing page", name, error)
            continue
        found = sections(revision["wikitext"])
        taken = 0
        for section in SECTIONS:
            if section not in found or taken >= PER_PAGE:
                continue
            text, items = build_section(found[section])
            priced = sum(
                bool(re.search(r"\$\s?\d", i.get("price", "") + i.get("content", "")))
                for i in items
            )
            if not 3 <= len(items) <= 20 or len(text) > 12_000 or priced < 2:
                continue
            title = revision["title"]
            url = "https://en.wikivoyage.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
            sources.append(
                {
                    "id": f"wv-{len(sources) + 1:03d}",
                    "page": title,
                    "section": section,
                    "revision_id": revision["revid"],
                    "revision_timestamp": revision["timestamp"],
                    "url": f"{url}#{section}",
                    "permalink": f"https://en.wikivoyage.org/w/index.php?oldid={revision['revid']}",
                    "licence": "CC BY-SA 4.0",
                    "attribution": f'Wikivoyage contributors, "{title}", section "{section}"',
                    "city": title.split(" (")[0],
                    "state": state[name],
                    "text": text,
                    "listings": items,
                }
            )
            taken += 1
        if len(sources) >= MAX_SOURCES:
            break
    OUT.write_text(json.dumps(sources[:MAX_SOURCES], indent=1, ensure_ascii=False))
    print(len(sources[:MAX_SOURCES]), "sources from", len({s["page"] for s in sources}), "pages")


if __name__ == "__main__":
    main()
