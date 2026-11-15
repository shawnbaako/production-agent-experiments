"""Build the 12 candidate pools from English Wikivoyage listings.

    uv run --frozen python pools.py fetch     # read pages, pin revisions, write data/pools.json
    uv run --frozen python pools.py rebuild   # re-read the pinned revisions only

Selection rule, the same for every pool:

1. Pages: each root article, then every non-redirect sub-article under it ("Tokyo/Ginza"),
   in alphabetical order. New York uses the city article and its five borough articles as roots.
2. Listings: the listing templates of the pool's kind, in page order. Activity pools take
   {{see}} and {{do}} (and {{listing|type=see|do}}); hotel pools take {{sleep}}.
3. Eligible: cleaned description text of at least 100 characters, name not already taken.
4. Take listings round robin across the pages (the first eligible listing of every page, then
   the second of every page, ...) until 30 are taken.

Listing text: the name, the description cut at 800 characters, then one line of stated details
(area from the page title, address, hours, price) where present.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import mwparserfromhell

HERE = Path(__file__).resolve().parent
API = "https://en.wikivoyage.org/w/api.php"
UA = "production-agent-experiments/1.0 (research script)"
POOL_SIZE, MIN_CHARS, MAX_CHARS = 30, 100, 800
NYC = ["New York City", "Manhattan", "Brooklyn", "Queens", "The Bronx", "Staten Island"]
POOLS = [  # pool_id, destination, category, root articles
    ("rome-activity", "Rome, Italy", "activity", ["Rome"]),
    ("tokyo-activity", "Tokyo, Japan", "activity", ["Tokyo"]),
    ("kyoto-activity", "Kyoto, Japan", "activity", ["Kyoto"]),
    ("bangkok-activity", "Bangkok, Thailand", "activity", ["Bangkok"]),
    ("newyork-activity", "New York, United States", "activity", NYC),
    ("lisbon-activity", "Lisbon, Portugal", "activity", ["Lisbon"]),
    ("marrakech-activity", "Marrakech, Morocco", "activity", ["Marrakech"]),
    ("rio-activity", "Rio de Janeiro, Brazil", "activity", ["Rio de Janeiro"]),
    ("tokyo-hotel", "Tokyo, Japan", "hotel", ["Tokyo"]),
    ("newyork-hotel", "New York, United States", "hotel", NYC),
    ("lisbon-hotel", "Lisbon, Portugal", "hotel", ["Lisbon"]),
    ("dubai-hotel", "Dubai, United Arab Emirates", "hotel", ["Dubai"]),
]
KINDS = {"activity": {"see", "do"}, "hotel": {"sleep"}}


def api(**params: str) -> dict:
    query = urllib.parse.urlencode(params | {"format": "json", "formatversion": "2"})
    request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except OSError as error:
            if attempt == 3:
                raise
            retry_after = getattr(error, "headers", None) and error.headers.get("Retry-After")
            time.sleep(int(retry_after or 0) or 30 * (attempt + 1))
    raise AssertionError("unreachable")


def subpages(root: str) -> list[str]:
    data = api(
        action="query",
        list="allpages",
        apprefix=root + "/",
        apnamespace="0",
        apfilterredir="nonredirects",
        aplimit="max",
    )
    return sorted(p["title"] for p in data["query"]["allpages"])


def wikitext(titles: list[str], pinned: dict[str, int] | None) -> dict[str, tuple[str, int]]:
    """Each page's current revision, or its pinned revision, in batches of 20 pages."""
    out = {}
    for start in range(0, len(titles), 20):
        batch = titles[start : start + 20]
        key = (
            {"revids": "|".join(str(pinned[t]) for t in batch)}
            if pinned
            else {"titles": "|".join(batch)}
        )
        data = api(action="query", prop="revisions", rvprop="ids|content", rvslots="main", **key)
        for page in data["query"]["pages"]:
            revision = page["revisions"][0]
            out[page["title"]] = (revision["slots"]["main"]["content"], revision["revid"])
        time.sleep(2)
    return out


def clean(value: object) -> str:
    """Wikitext to plain text: an inline template keeps its positional arguments ({{km|5}})."""
    code = mwparserfromhell.parse(str(value))
    for template in code.filter_templates(recursive=False):
        args = " ".join(str(p.value).strip() for p in template.params if not p.showkey)
        try:
            code.replace(template, args)
        except ValueError:
            continue
    text = code.strip_code(normalize=True, collapse=True)
    return " ".join(text.replace("'''", "").replace("''", "").split())


def listings(text: str, title: str, kinds: set[str]) -> list[dict]:
    out = []
    for template in mwparserfromhell.parse(text).filter_templates():
        kind = str(template.name).strip().lower()
        get = {str(p.name).strip(): p.value for p in template.params if p.showkey}
        if kind == "listing":
            kind = clean(get.get("type", "")).lower()
        if kind not in kinds:
            continue
        name, content = clean(get.get("name", "")), clean(get.get("content", ""))
        if not name or len(content) < MIN_CHARS:
            continue
        area = title.split("/")[-1]
        details = [f"Area: {area}"]
        for field in ("address", "hours", "price"):
            if value := clean(get.get(field, "")):
                details.append(f"{field.capitalize()}: {value}")
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS].rsplit(" ", 1)[0] + " …"
        out.append({"name": name, "text": f"{name}\n{content}\n" + "; ".join(details)})
    return out


def build(pinned: dict[str, int] | None = None) -> None:
    pages: dict[str, int] = {}
    texts: dict[str, str] = {}
    pools = []
    for pool_id, destination, category, roots in POOLS:
        titles = [t for root in roots for t in [root, *subpages(root)]] if not pinned else None
        if pinned:  # the pool's page list is the pinned list, in its recorded order
            titles = next(
                p["pages"]
                for p in json.loads((HERE / "data/pools.json").read_text())
                if p["pool_id"] == pool_id
            )
        missing = [t for t in titles if t not in texts]
        for title, (text, revid) in wikitext(missing, pinned).items():
            texts[title], pages[title] = text, revid
        per_page = [(t, listings(texts[t], t, KINDS[category])) for t in titles]
        chosen, names = [], set()
        for depth in range(max(len(found) for _, found in per_page)):
            for title, found in per_page:
                if depth < len(found) and len(chosen) < POOL_SIZE:
                    item = found[depth]
                    if item["name"].casefold() in names:
                        continue
                    names.add(item["name"].casefold())
                    candidate_id = hashlib.sha256(f"{title}\n{item['name']}".encode()).hexdigest()
                    chosen.append(
                        {
                            "cid": candidate_id[:12],
                            "name": item["name"],
                            "text": item["text"],
                            "page": title,
                            "revid": pages[title],
                        }
                    )
        pools.append(
            {
                "pool_id": pool_id,
                "destination": destination,
                "category": category,
                "pages": titles,
                "candidates": chosen,
            }
        )
        print(pool_id, len(titles), "pages", len(chosen), "listings", file=sys.stderr)
    (HERE / "data/pools.json").write_text(json.dumps(pools, ensure_ascii=False, indent=1) + "\n")
    used = sorted({c["page"] for p in pools for c in p["candidates"]} | set(pages))
    (HERE / "data/pages.json").write_text(
        json.dumps({t: pages[t] for t in used}, ensure_ascii=False, indent=1) + "\n"
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        build()
    elif sys.argv[1:] == ["rebuild"]:
        build(json.loads((HERE / "data/pages.json").read_text()))
    else:
        raise SystemExit(__doc__)
