"""The fixed public query set for mix.py.

Each query has `must`: a list of groups, each group a list of alternatives. A result is on topic when
every group has at least one alternative in its title, snippet or URL (lower case). This is a rough
relevance measure on purpose: it catches the failure that matters for an agent, a page about
something else, and nothing finer.

Three kinds:
  named   a quoted organisation or product name that collides with a commoner word or a famous
          namesake. This is the shape of most searches a research agent makes for a named company.
  tech    a technical question with distinctive terms.
  recent  a topic where a person would plausibly ask for recent results, so a date filter is natural.
"""

QUERIES = [
    # named
    {"id": "n01", "kind": "named", "q": '"Mercury Insurance" auto claims', "must": [["mercury insurance"]]},
    {"id": "n02", "kind": "named", "q": '"Phoenix Contact" terminal blocks', "must": [["phoenix contact"]]},
    {"id": "n03", "kind": "named", "q": '"Apache Arrow" Flight SQL', "must": [["arrow"], ["flight"]]},
    {"id": "n04", "kind": "named", "q": '"Rocky Mountain Institute" heat pumps',
     "must": [["rocky mountain institute", "rmi.org"]]},
    {"id": "n05", "kind": "named", "q": '"Fraunhofer ISE" agrivoltaics', "must": [["fraunhofer"]]},
    {"id": "n06", "kind": "named", "q": '"Ordnance Survey" maps API', "must": [["ordnance survey", "ordnancesurvey"]]},
    {"id": "n07", "kind": "named", "q": '"Worn Wear" Patagonia repairs', "must": [["worn wear", "wornwear"]]},
    {"id": "n08", "kind": "named", "q": '"Blue Origin" New Glenn', "must": [["new glenn"]]},
    # tech
    {"id": "t01", "kind": "tech", "q": "python asyncio semaphore", "must": [["asyncio"], ["semaphore"]]},
    {"id": "t02", "kind": "tech", "q": "postgresql row level security policy",
     "must": [["postgres"], ["row level security", "row-level security", "rls"]]},
    {"id": "t03", "kind": "tech", "q": "searxng time_range engines", "must": [["searxng"]]},
    {"id": "t04", "kind": "tech", "q": "rust borrow checker lifetimes", "must": [["borrow"], ["lifetime"]]},
    {"id": "t05", "kind": "tech", "q": "kubernetes pod disruption budget", "must": [["disruption budget", "poddisruptionbudget"]]},
    {"id": "t06", "kind": "tech", "q": "sqlite wal checkpoint", "must": [["sqlite"], ["wal", "write-ahead"]]},
    # recent
    {"id": "r01", "kind": "recent", "q": "Python 3.15 release", "must": [["python"], ["3.15"]]},
    {"id": "r02", "kind": "recent", "q": "Linux kernel release", "must": [["kernel"]]},
    {"id": "r03", "kind": "recent", "q": "Firefox release notes", "must": [["firefox"]]},
    {"id": "r04", "kind": "recent", "q": "NASA Artemis mission", "must": [["artemis"]]},
    {"id": "r05", "kind": "recent", "q": "European Central Bank interest rate decision",
     "must": [["ecb", "european central bank"]]},
    {"id": "r06", "kind": "recent", "q": "wildfire evacuation orders", "must": [["wildfire", "fire"]]},
]
