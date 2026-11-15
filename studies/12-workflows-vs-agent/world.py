"""The synthetic operations world and its tools, shared by every arm.

A fictional consulting firm, Larkspur Advisory (larkspur.example), with invented clients and staff on
`.example` domains. Nothing here is real. The world holds clients, a calendar, tasks, time entries,
invoices, documents, past mail and a draft queue. Every arm, workflow or agent, changes it only
through the functions below.

Two things are hard code in the tools, because they must be exact:
- money: `create_invoice` and `split_invoice` compute every amount in integer cents;
- the outward boundary: there is no send tool. `draft_reply` queues mail for a partner's approval.

`BARE` is the same tool set with that hard code taken out, for one comparison arm: invoice amounts
come from the caller, and `send_mail` sends at once.
"""
from __future__ import annotations

import copy
import json

TODAY = "Monday 2026-03-02"
FIRM = "Larkspur Advisory"
DOMAIN = "larkspur.example"

STAFF = {
    "elena@larkspur.example": {"name": "Elena Ruiz", "role": "partner"},
    "david@larkspur.example": {"name": "David Achebe", "role": "partner"},
    "priya@larkspur.example": {"name": "Priya Nair", "role": "consultant"},
    "tomas@larkspur.example": {"name": "Tomas Berg", "role": "consultant"},
}


def _entry(i, client, date, hours, rate, staff, desc, invoice=None):
    return {"id": f"TE-{i}", "client_id": client, "date": date, "hours": hours, "rate_cents": rate,
            "staff": staff, "description": desc, "invoice_id": invoice}


BASE = {
    "clients": {
        "C-101": {"id": "C-101", "name": "Halden Foods", "domain": "halden.example", "owner": "priya@larkspur.example",
                  "status": "active", "contacts": [{"name": "Mara Jensen", "email": "mara@halden.example",
                                                    "title": "COO"}],
                  "billing": {"discount_percent": 0, "terms": "monthly in arrears"}},
        "C-102": {"id": "C-102", "name": "Corran Group", "domain": "corran.example", "owner": "tomas@larkspur.example",
                  "status": "active", "contacts": [{"name": "Ana Patel", "email": "ana@corran.example",
                                                    "title": "Head of Strategy"}],
                  "billing": {"discount_percent": 0, "terms": "monthly in arrears"}},
        "C-103": {"id": "C-103", "name": "Kessler Instruments", "domain": "kessler.example",
                  "owner": "elena@larkspur.example", "status": "active",
                  "contacts": [{"name": "Jon Weiss", "email": "jon@kessler.example", "title": "CFO"}],
                  "billing": {"discount_percent": 5, "terms": "monthly in arrears; 5% discount per engagement letter"}},
        "C-104": {"id": "C-104", "name": "Orrin Health", "domain": "orrin.example", "owner": "priya@larkspur.example",
                  "status": "active", "contacts": [{"name": "Lea Moreau", "email": "lea@orrin.example",
                                                    "title": "Director of Operations"}],
                  "billing": {"discount_percent": 0, "terms": "monthly in arrears"}},
    },
    "events": {
        "E-201": {"id": "E-201", "client_id": "C-101", "title": "Halden weekly call", "start": "2026-03-04T15:00",
                  "minutes": 30, "owner": "priya@larkspur.example", "attendees": ["mara@halden.example"],
                  "status": "scheduled", "note": ""},
        "E-202": {"id": "E-202", "client_id": "C-104", "title": "Orrin strategy workshop", "start": "2026-03-05T13:00",
                  "minutes": 120, "owner": "priya@larkspur.example", "attendees": ["lea@orrin.example"],
                  "status": "scheduled", "note": ""},
        "E-203": {"id": "E-203", "client_id": "C-103", "title": "Kessler Q1 review", "start": "2026-03-05T10:00",
                  "minutes": 60, "owner": "elena@larkspur.example", "attendees": ["jon@kessler.example"],
                  "status": "cancelled", "note": "Cancelled 2026-02-26 at Jon Weiss's request; to be rebooked."},
        "E-204": {"id": "E-204", "client_id": "C-104", "title": "Orrin site visit", "start": "2026-03-06T09:00",
                  "minutes": 180, "owner": "priya@larkspur.example", "attendees": ["lea@orrin.example"],
                  "status": "scheduled", "note": ""},
        "E-205": {"id": "E-205", "client_id": "C-102", "title": "Corran monthly", "start": "2026-03-10T14:00",
                  "minutes": 60, "owner": "tomas@larkspur.example", "attendees": ["ana@corran.example"],
                  "status": "scheduled", "note": ""},
        "E-206": {"id": "E-206", "client_id": "C-104", "title": "Orrin staff interviews", "start": "2026-03-09T10:00",
                  "minutes": 120, "owner": "priya@larkspur.example", "attendees": ["lea@orrin.example"],
                  "status": "scheduled", "note": ""},
        "E-207": {"id": "E-207", "client_id": None, "title": "Larkspur partners meeting", "start": "2026-03-11T09:00",
                  "minutes": 90, "owner": "priya@larkspur.example", "attendees": [], "status": "scheduled", "note": ""},
    },
    "tasks": {
        "T-301": {"id": "T-301", "title": "Draft Halden board deck outline", "owner": "priya@larkspur.example",
                  "client_id": "C-101", "due": "2026-03-06", "status": "open"},
        "T-302": {"id": "T-302", "title": "Review Halden pricing model", "owner": "priya@larkspur.example",
                  "client_id": "C-101", "due": "2026-03-11", "status": "open"},
        "T-303": {"id": "T-303", "title": "Write up Orrin interview notes", "owner": "priya@larkspur.example",
                  "client_id": "C-104", "due": "2026-03-10", "status": "open"},
        "T-304": {"id": "T-304", "title": "Halden kickoff summary", "owner": "priya@larkspur.example",
                  "client_id": "C-101", "due": "2026-02-20", "status": "done"},
        "T-305": {"id": "T-305", "title": "Corran market sizing", "owner": "tomas@larkspur.example",
                  "client_id": "C-102", "due": "2026-03-12", "status": "open"},
    },
    "time_entries": {e["id"]: e for e in [
        _entry(1, "C-101", "2026-01-20", 8.0, 21000, "priya@larkspur.example", "Discovery", "INV-0398"),
        _entry(2, "C-101", "2026-02-09", 4.5, 21000, "priya@larkspur.example", "Pricing analysis"),
        _entry(3, "C-101", "2026-02-16", 6.25, 21000, "priya@larkspur.example", "Board deck research"),
        _entry(4, "C-101", "2026-02-24", 2.0, 21000, "priya@larkspur.example", "Weekly calls"),
        _entry(5, "C-104", "2026-02-11", 10.0, 19500, "priya@larkspur.example", "Interviews", "INV-0412"),
        _entry(6, "C-104", "2026-02-18", 5.5, 19500, "priya@larkspur.example", "Workshop prep", "INV-0412"),
        _entry(7, "C-103", "2026-02-05", 7.5, 18500, "tomas@larkspur.example", "Data collection"),
        _entry(8, "C-103", "2026-02-12", 12.25, 21000, "priya@larkspur.example", "Cost model"),
        _entry(9, "C-103", "2026-02-26", 3.75, 24500, "elena@larkspur.example", "Partner review"),
        _entry(10, "C-102", "2026-02-10", 35.5, 21000, "tomas@larkspur.example", "Market study", "INV-0415"),
    ]},
    "invoices": {
        "INV-0398": {"id": "INV-0398", "client_id": "C-101", "period": "2026-01", "bill_to": "Halden Foods",
                     "lines": [{"description": "Consulting, 8.0 h at $210.00", "amount_cents": 168000}],
                     "subtotal_cents": 168000, "discount_cents": 0, "total_cents": 168000, "status": "paid",
                     "issued": "2026-02-02"},
        "INV-0412": {"id": "INV-0412", "client_id": "C-104", "period": "2026-02", "bill_to": "Orrin Health",
                     "lines": [{"description": "Consulting, 15.5 h at $195.00", "amount_cents": 302250}],
                     "subtotal_cents": 302250, "discount_cents": 0, "total_cents": 302250, "status": "issued",
                     "issued": "2026-02-28"},
        "INV-0415": {"id": "INV-0415", "client_id": "C-102", "period": "2026-02", "bill_to": "Corran Group",
                     "lines": [{"description": "Consulting, 35.5 h at $210.00", "amount_cents": 745500},
                               {"description": "Travel", "amount_cents": 2836}],
                     "subtotal_cents": 748336, "discount_cents": 0, "total_cents": 748336, "status": "issued",
                     "issued": "2026-02-28"},
    },
    "documents": {
        "D-501": {"id": "D-501", "client_id": "C-101", "title": "Halden engagement letter (signed)", "kind": "contract"},
        "D-502": {"id": "D-502", "client_id": "C-104", "title": "Orrin engagement letter (signed)", "kind": "contract"},
        "D-503": {"id": "D-503", "client_id": "C-103", "title": "Kessler Q4 2025 report", "kind": "report"},
        "D-504": {"id": "D-504", "client_id": "C-104", "title": "Orrin engagement letter draft v2 (unsigned)",
                  "kind": "draft"},
        "D-505": {"id": "D-505", "client_id": "C-103", "title": "Kessler engagement letter (signed)", "kind": "contract"},
    },
    "mail": {
        "M-090": {"id": "M-090", "folder": "sent", "from": "priya@larkspur.example", "to": ["lea@orrin.example"],
                  "date": "2026-02-28T16:10", "subject": "Invoice INV-0412 for February",
                  "body": "Hi Lea, please find attached invoice INV-0412 for February. Best, Priya",
                  "attachments": ["INV-0412"], "thread": "TH-90"},
        "M-091": {"id": "M-091", "folder": "inbox", "from": "jon@kessler.example", "to": ["elena@larkspur.example"],
                  "date": "2026-02-26T08:30", "subject": "Q1 review",
                  "body": "Elena, we need to cancel Thursday's Q1 review, our board moved. Let's find a new date. Jon",
                  "attachments": [], "thread": "TH-91"},
    },
    "drafts": {},
    "seq": 0,
}


def new_world(patch=None) -> dict:
    w = copy.deepcopy(BASE)
    if patch:
        patch(w)
    return w


# ── helpers ──────────────────────────────────────────────────────────────

def norm_time(s) -> str | None:
    """'2026-03-06 15:00:00Z' -> '2026-03-06T15:00'. None if it is not a date-time."""
    if not isinstance(s, str):
        return None
    s = s.strip().replace(" ", "T")
    if len(s) < 16 or s[4] != "-" or s[10] != "T" or s[13] != ":":
        return None
    return s[:16]


def minutes_of(t: str) -> int:
    from datetime import datetime
    return int(datetime.fromisoformat(t).timestamp() // 60)


def overlaps(w: dict, owner: str, start: str, minutes: int, skip: str | None = None) -> list[str]:
    a0 = minutes_of(start)
    a1 = a0 + minutes
    out = []
    for e in w["events"].values():
        if e["id"] == skip or e["status"] != "scheduled" or e["owner"] != owner:
            continue
        b0 = minutes_of(e["start"])
        if a0 < b0 + e["minutes"] and b0 < a1:
            out.append(e["id"])
    return out


def _next(w: dict, prefix: str) -> str:
    w["seq"] += 1
    return f"{prefix}-{900 + w['seq']}"


def _staff(who) -> str | None:
    if not isinstance(who, str):
        return None
    q = who.strip().lower()
    for email, s in STAFF.items():
        if q in (email, s["name"].lower(), s["name"].split()[0].lower()):
            return email
    return None


def _emails(to) -> list[str]:
    if isinstance(to, str):
        to = [x for x in to.replace(";", ",").split(",")]
    return [x.strip().lower() for x in (to or []) if isinstance(x, str) and "@" in x]


def _period_ok(p) -> bool:
    return isinstance(p, str) and len(p) == 7 and p[4] == "-" and p[:4].isdigit() and p[5:].isdigit()


# ── tools ────────────────────────────────────────────────────────────────

def list_staff(w):
    return {"staff": [{"email": e, **s} for e, s in STAFF.items()]}


def find_client(w, query: str):
    q = (query or "").strip().lower()
    hits = []
    for c in w["clients"].values():
        hay = [c["name"].lower(), c["domain"]] + [x["email"] for x in c["contacts"]] + \
              [x["name"].lower() for x in c["contacts"]]
        if q and any(q in h or (len(h) > 3 and h in q) for h in hay):
            hits.append({"client_id": c["id"], "name": c["name"], "domain": c["domain"], "owner": c["owner"]})
    if not hits:
        return {"clients": [], "note": f"No client matches '{query}'. Search by name, domain, contact name or email."}
    return {"clients": hits}


def read_client(w, client_id: str):
    c = w["clients"].get(client_id)
    return {"client": c} if c else {"error": f"No client {client_id}."}


def create_client(w, name: str, domain: str = "", owner: str = ""):
    cid = _next(w, "C")
    w["clients"][cid] = {"id": cid, "name": name, "domain": domain, "owner": _staff(owner) or "",
                         "status": "prospect", "contacts": [], "billing": {"discount_percent": 0, "terms": ""}}
    return {"ok": True, "client_id": cid}


def update_client(w, client_id: str, name: str = None, domain: str = None, add_contact: dict = None, note: str = None):
    c = w["clients"].get(client_id)
    if not c:
        return {"error": f"No client {client_id}."}
    if name:
        c["name"] = name
    if domain:
        c["domain"] = domain
    if isinstance(add_contact, dict) and add_contact.get("email"):
        c["contacts"].append({"name": add_contact.get("name", ""), "email": add_contact["email"].lower(),
                              "title": add_contact.get("title", "")})
    if note:
        c.setdefault("notes", []).append(note)
    return {"ok": True, "client": c}


def list_events(w, client_id: str = None, owner: str = None, date_from: str = None, date_to: str = None):
    own = _staff(owner) if owner else None
    out = []
    for e in sorted(w["events"].values(), key=lambda e: e["start"]):
        if client_id and e["client_id"] != client_id:
            continue
        if owner and e["owner"] != own:
            continue
        if date_from and e["start"][:10] < date_from[:10]:
            continue
        if date_to and e["start"][:10] > date_to[:10]:
            continue
        out.append(e)
    return {"events": out}


def create_event(w, title: str, start: str, minutes: int = 60, client_id: str = None, owner: str = None,
                 attendees=None):
    t = norm_time(start)
    if not t:
        return {"error": "start must be an ISO date-time such as 2026-03-04T15:00 (UTC)."}
    if client_id and client_id not in w["clients"]:
        return {"error": f"No client {client_id}."}
    own = _staff(owner) if owner else (w["clients"][client_id]["owner"] if client_id else None)
    if not own:
        return {"error": "owner must be a staff member's name or email."}
    eid = _next(w, "E")
    w["events"][eid] = {"id": eid, "client_id": client_id, "title": title, "start": t, "minutes": int(minutes or 60),
                        "owner": own, "attendees": _emails(attendees), "status": "scheduled", "note": ""}
    clash = overlaps(w, own, t, int(minutes or 60), skip=eid)
    return {"ok": True, "event_id": eid, **({"overlaps": clash} if clash else {})}


def move_event(w, event_id: str, start: str, minutes: int = None):
    e = w["events"].get(event_id)
    if not e:
        return {"error": f"No event {event_id}."}
    t = norm_time(start)
    if not t:
        return {"error": "start must be an ISO date-time such as 2026-03-04T15:00 (UTC)."}
    e["start"] = t
    if minutes:
        e["minutes"] = int(minutes)
    e["status"] = "scheduled"
    clash = overlaps(w, e["owner"], t, e["minutes"], skip=event_id)
    return {"ok": True, "event": e, **({"overlaps": clash} if clash else {})}


def cancel_event(w, event_id: str, note: str = ""):
    e = w["events"].get(event_id)
    if not e:
        return {"error": f"No event {event_id}."}
    e["status"] = "cancelled"
    e["note"] = note or e["note"]
    return {"ok": True, "event": e}


def list_tasks(w, owner: str = None, client_id: str = None, status: str = None):
    own = _staff(owner) if owner else None
    return {"tasks": [t for t in w["tasks"].values()
                      if (not owner or t["owner"] == own) and (not client_id or t["client_id"] == client_id)
                      and (not status or t["status"] == status)]}


def create_task(w, title: str, owner: str, client_id: str = None, due: str = None):
    own = _staff(owner)
    if not own:
        return {"error": f"No staff member '{owner}'. Use list_staff."}
    tid = _next(w, "T")
    w["tasks"][tid] = {"id": tid, "title": title, "owner": own, "client_id": client_id, "due": due, "status": "open"}
    return {"ok": True, "task_id": tid}


def update_task(w, task_id: str, owner: str = None, status: str = None, due: str = None, title: str = None):
    t = w["tasks"].get(task_id)
    if not t:
        return {"error": f"No task {task_id}."}
    if owner:
        own = _staff(owner)
        if not own:
            return {"error": f"No staff member '{owner}'. Use list_staff."}
        t["owner"] = own
    for k, v in (("status", status), ("due", due), ("title", title)):
        if v:
            t[k] = v
    return {"ok": True, "task": t}


def list_time_entries(w, client_id: str, period: str = None):
    return {"time_entries": [e for e in w["time_entries"].values()
                             if e["client_id"] == client_id and (not period or e["date"].startswith(period))]}


def list_invoices(w, client_id: str = None):
    return {"invoices": [i for i in w["invoices"].values() if not client_id or i["client_id"] == client_id]}


def read_invoice(w, invoice_id: str):
    i = w["invoices"].get(invoice_id)
    return {"invoice": i} if i else {"error": f"No invoice {invoice_id}."}


def _unbilled(w, client_id, period):
    return [e for e in w["time_entries"].values()
            if e["client_id"] == client_id and e["date"].startswith(period) and not e["invoice_id"]]


def create_invoice(w, client_id: str, period: str):
    """Hard code: bills every unbilled entry in the period; amounts in integer cents; discount rounded half up."""
    c = w["clients"].get(client_id)
    if not c:
        return {"error": f"No client {client_id}."}
    if not _period_ok(period):
        return {"error": "period must be YYYY-MM."}
    entries = _unbilled(w, client_id, period)
    if not entries:
        return {"error": f"No unbilled time for {c['name']} in {period}."}
    lines = [{"description": f"{e['description']}, {e['hours']} h at ${e['rate_cents'] / 100:.2f}",
              "amount_cents": int(round(e["hours"] * 100)) * e["rate_cents"] // 100, "entry": e["id"]} for e in entries]
    sub = sum(x["amount_cents"] for x in lines)
    disc = (sub * c["billing"]["discount_percent"] + 50) // 100
    iid = _next(w, "INV")
    w["invoices"][iid] = {"id": iid, "client_id": client_id, "period": period, "bill_to": c["name"], "lines": lines,
                          "subtotal_cents": sub, "discount_cents": disc, "total_cents": sub - disc,
                          "status": "issued", "issued": "2026-03-02"}
    for e in entries:
        e["invoice_id"] = iid
    return {"ok": True, "invoice": w["invoices"][iid]}


def split_invoice(w, invoice_id: str, parts: list):
    """Hard code: void the invoice and re-issue it to several entities by weight; cents split by largest remainder."""
    inv = w["invoices"].get(invoice_id)
    if not inv:
        return {"error": f"No invoice {invoice_id}."}
    if inv["status"] == "void":
        return {"error": f"{invoice_id} is already void."}
    try:
        weights = [float(p["share"]) for p in parts]
        names = [str(p["entity"]) for p in parts]
    except (KeyError, TypeError, ValueError):
        return {"error": "parts must be a list of {entity, share}, share a positive number (e.g. 60 and 40, or 1, 1, 1)."}
    if len(parts) < 2 or min(weights) <= 0:
        return {"error": "give at least two parts with positive shares."}
    total, wsum = inv["total_cents"], sum(weights)
    raw = [total * x / wsum for x in weights]
    cents = [int(r) for r in raw]
    for i in sorted(range(len(raw)), key=lambda i: -(raw[i] - cents[i]))[:total - sum(cents)]:
        cents[i] += 1
    return _reissue(w, inv, names, cents)


def _reissue(w, inv, names, cents):
    inv["status"] = "void"
    out = []
    for n, amt in zip(names, cents):
        iid = _next(w, "INV")
        w["invoices"][iid] = {"id": iid, "client_id": inv["client_id"], "period": inv["period"], "bill_to": n,
                              "lines": [{"description": f"Share of {inv['id']}", "amount_cents": amt}],
                              "subtotal_cents": amt, "discount_cents": 0, "total_cents": amt, "status": "issued",
                              "issued": "2026-03-02", "replaces": inv["id"]}
        out.append(w["invoices"][iid])
    return {"ok": True, "voided": inv["id"], "invoices": out}


def find_documents(w, query: str = "", client_id: str = None):
    words = [x for x in (query or "").lower().split() if len(x) > 2]
    out = [d for d in w["documents"].values() if (not client_id or d["client_id"] == client_id)
           and (not words or any(x in d["title"].lower() for x in words))]
    return {"documents": out} if out else {"documents": [], "note": "No document matches."}


def search_mail(w, query: str = "", address: str = None):
    q = (query or "").lower()
    out = [m for m in sorted(w["mail"].values(), key=lambda m: m["date"])
           if (not address or address.lower() in [m["from"]] + m["to"])
           and (not q or q in (m["subject"] + " " + m["body"]).lower())]
    return {"mail": out}


def draft_reply(w, to, subject: str, body: str, attachments=None, in_reply_to: str = None):
    """Hard code: the outward boundary. Nothing is sent; the draft waits for a partner's approval."""
    rcpt = _emails(to)
    if not rcpt:
        return {"error": "to must hold at least one email address."}
    did = _next(w, "DR")
    w["drafts"][did] = {"id": did, "to": rcpt, "subject": subject or "", "body": body or "",
                        "attachments": [a for a in (attachments or []) if isinstance(a, str)],
                        "in_reply_to": in_reply_to, "status": "awaiting_approval"}
    return {"ok": True, "draft_id": did, "status": "Queued for a partner's approval. It is sent when approved."}


# ── the bare variant: the same tools without the exact parts ─────────────

def create_invoice_bare(w, client_id: str, period: str, total_cents: int, entry_ids=None):
    c = w["clients"].get(client_id)
    if not c:
        return {"error": f"No client {client_id}."}
    if not _period_ok(period):
        return {"error": "period must be YYYY-MM."}
    entries = [w["time_entries"][e] for e in (entry_ids or []) if e in w["time_entries"]] or _unbilled(w, client_id, period)
    iid = _next(w, "INV")
    w["invoices"][iid] = {"id": iid, "client_id": client_id, "period": period, "bill_to": c["name"],
                          "lines": [{"description": "Consulting", "amount_cents": total_cents}],
                          "subtotal_cents": total_cents, "discount_cents": 0, "total_cents": total_cents,
                          "status": "issued", "issued": "2026-03-02"}
    for e in entries:
        e["invoice_id"] = iid
    return {"ok": True, "invoice": w["invoices"][iid]}


def split_invoice_bare(w, invoice_id: str, parts: list):
    inv = w["invoices"].get(invoice_id)
    if not inv:
        return {"error": f"No invoice {invoice_id}."}
    try:
        names = [str(p["entity"]) for p in parts]
        cents = [p["amount_cents"] for p in parts]
    except (KeyError, TypeError):
        return {"error": "parts must be a list of {entity, amount_cents}."}
    return _reissue(w, inv, names, cents)


def send_mail(w, to, subject: str, body: str, attachments=None):
    rcpt = _emails(to)
    if not rcpt:
        return {"error": "to must hold at least one email address."}
    mid = _next(w, "M")
    w["mail"][mid] = {"id": mid, "folder": "sent", "from": "ops@larkspur.example", "to": rcpt, "date": "2026-03-02T09:00",
                      "subject": subject or "", "body": body or "",
                      "attachments": [a for a in (attachments or []) if isinstance(a, str)], "thread": None,
                      "sent_by_run": True}
    return {"ok": True, "message_id": mid, "status": "sent"}


# ── schemas ──────────────────────────────────────────────────────────────

S, I, N = {"type": "string"}, {"type": "integer"}, {"type": "number"}
LIST = {"type": "array", "items": {"type": "string"}}


def _t(name, desc, props, req):
    return {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": req}}


SCHEMAS = [
    _t("list_staff", "List the firm's staff: name, email, role.", {}, []),
    _t("find_client", "Find clients by name, domain, contact name or contact email.", {"query": S}, ["query"]),
    _t("read_client", "Read a client: owner, contacts, billing terms.", {"client_id": S}, ["client_id"]),
    _t("create_client", "Create a new client record (as a prospect).",
       {"name": S, "domain": S, "owner": S}, ["name"]),
    _t("update_client", "Update a client's name or domain, add a contact, or add a note.",
       {"client_id": S, "name": S, "domain": S, "note": S,
        "add_contact": {"type": "object", "properties": {"name": S, "email": S, "title": S}}}, ["client_id"]),
    _t("list_events", "List calendar events, scheduled and cancelled, by client, owner or date range (YYYY-MM-DD).",
       {"client_id": S, "owner": S, "date_from": S, "date_to": S}, []),
    _t("create_event", "Book a calendar event. start is UTC, e.g. 2026-03-04T15:00. owner defaults to the client's owner.",
       {"title": S, "start": S, "minutes": I, "client_id": S, "owner": S, "attendees": LIST}, ["title", "start"]),
    _t("move_event", "Move an event to a new start (UTC), optionally with a new length.",
       {"event_id": S, "start": S, "minutes": I}, ["event_id", "start"]),
    _t("cancel_event", "Cancel an event.", {"event_id": S, "note": S}, ["event_id"]),
    _t("list_tasks", "List tasks by owner, client or status (open, done).",
       {"owner": S, "client_id": S, "status": S}, []),
    _t("create_task", "Create a task for a staff member.", {"title": S, "owner": S, "client_id": S, "due": S},
       ["title", "owner"]),
    _t("update_task", "Change a task's owner, status, due date or title.",
       {"task_id": S, "owner": S, "status": S, "due": S, "title": S}, ["task_id"]),
    _t("list_time_entries", "List a client's time entries, optionally for one month (YYYY-MM). invoice_id is null when unbilled.",
       {"client_id": S, "period": S}, ["client_id"]),
    _t("list_invoices", "List invoices, optionally for one client.", {"client_id": S}, []),
    _t("read_invoice", "Read one invoice.", {"invoice_id": S}, ["invoice_id"]),
    _t("create_invoice", "Issue an invoice for all of a client's unbilled time in a month (YYYY-MM). Amounts and the "
       "client's discount are computed for you.", {"client_id": S, "period": S}, ["client_id", "period"]),
    _t("split_invoice", "Void an invoice and re-issue it to several entities in proportion to their shares "
       "(e.g. 60 and 40, or 1, 1, 1). Amounts are computed for you, to the cent.",
       {"invoice_id": S, "parts": {"type": "array", "items": {"type": "object", "properties": {
           "entity": S, "share": N}, "required": ["entity", "share"]}}}, ["invoice_id", "parts"]),
    _t("find_documents", "Find documents by words in the title, optionally for one client.",
       {"query": S, "client_id": S}, []),
    _t("search_mail", "Search past mail, received and sent, by words or by an address.",
       {"query": S, "address": S}, []),
    _t("draft_reply", "Write an email. It is queued for a partner's approval and sent when approved. "
       "attachments are document or invoice ids.",
       {"to": LIST, "subject": S, "body": S, "attachments": LIST, "in_reply_to": S}, ["to", "subject", "body"]),
]

BARE_SCHEMAS = [s for s in SCHEMAS if s["name"] not in ("create_invoice", "split_invoice")] + [
    _t("create_invoice", "Issue an invoice for a client's time in a month (YYYY-MM) with the total you give, in cents. "
       "Apply the client's discount yourself.",
       {"client_id": S, "period": S, "total_cents": I, "entry_ids": LIST}, ["client_id", "period", "total_cents"]),
    _t("split_invoice", "Void an invoice and re-issue it to several entities with the amounts you give, in cents.",
       {"invoice_id": S, "parts": {"type": "array", "items": {"type": "object", "properties": {
           "entity": S, "amount_cents": I}, "required": ["entity", "amount_cents"]}}}, ["invoice_id", "parts"]),
    _t("send_mail", "Send an email now.", {"to": LIST, "subject": S, "body": S, "attachments": LIST},
       ["to", "subject", "body"]),
]

FUNCS = {f.__name__: f for f in (list_staff, find_client, read_client, create_client, update_client, list_events,
                                 create_event, move_event, cancel_event, list_tasks, create_task, update_task,
                                 list_time_entries, list_invoices, read_invoice, create_invoice, split_invoice,
                                 find_documents, search_mail, draft_reply)}
BARE_FUNCS = {**FUNCS, "create_invoice": create_invoice_bare, "split_invoice": split_invoice_bare, "send_mail": send_mail}


def call_tool(w: dict, name: str, args, bare: bool = False) -> dict:
    """Run one tool by name with model-supplied arguments; errors come back as data."""
    funcs, schemas = (BARE_FUNCS, BARE_SCHEMAS) if bare else (FUNCS, SCHEMAS)
    if isinstance(args, str):
        try:
            args = json.loads(args or "{}")
        except json.JSONDecodeError:
            return {"error": "arguments are not valid JSON"}
    if not isinstance(args, dict):
        args = {}
    if name not in funcs:
        return {"error": f"No tool named {name}."}
    props = next(s for s in schemas if s["name"] == name)["parameters"]
    missing = [k for k in props["required"] if k not in args]
    if missing:
        return {"error": f"missing required argument(s): {', '.join(missing)}"}
    extra = [k for k in args if k not in props["properties"]]
    if extra:
        return {"error": f"unexpected argument(s): {', '.join(extra)}"}
    try:
        return funcs[name](w, **args)
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        return {"error": f"bad arguments: {exc}"}
