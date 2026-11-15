"""Arm `workflow`: a deterministic pipeline with a model used only at fixed steps.

This is how a workflow framework would handle the inbox: fixed step order, rule-based routing, and a model
asked three narrow things: classify the message into one of a fixed set of categories, extract that
category's fields as JSON, and write the body of a reply from facts the code supplies. Everything else is
code: client lookup, which record to change, what to book, who to answer. Anything the routes do not
cover is handed back to a person. It uses the same tools as the agent (world.py), so the exact parts
(invoice arithmetic, mail only through approval) are the same.

It was written for the on-script tasks in cases.py, before any model was run.
"""
from __future__ import annotations

import json
import re

import world as W

CATEGORIES = ["meeting_request", "reschedule_meeting", "cancel_meeting", "invoice_request", "document_request",
              "task_request", "other"]

FIELDS = {
    "meeting_request": '{"client_name": str|null, "start": "YYYY-MM-DDTHH:MM" (UTC)|null, "minutes": int|null}',
    "reschedule_meeting": '{"client_name": str|null, "original_date": "YYYY-MM-DD"|null, '
                          '"new_start": "YYYY-MM-DDTHH:MM" (UTC)|null}',
    "cancel_meeting": '{"client_name": str|null, "date": "YYYY-MM-DD"|null}',
    "invoice_request": '{"client_name": str|null, "period": "YYYY-MM"|null}',
    "document_request": '{"client_name": str|null, "document": str}',
    "task_request": '{"title": str, "owner": str, "client_name": str|null, "due": "YYYY-MM-DD"|null}',
}


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        v = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return v if isinstance(v, dict) else {}


def show(msg: dict) -> str:
    return f"From: {msg['from']}\nSubject: {msg['subject']}\n\n{msg['body']}"


class Workflow:
    categories = CATEGORIES

    def __init__(self, ctx, w: dict):
        self.ctx, self.w, self.log = ctx, w, []

    def tool(self, name, **args):
        out = W.call_tool(self.w, name, args)
        self.log.append({"tool": name, "args": args, "ok": "error" not in out})
        return out

    # ── the three model steps ──
    def classify(self, msg) -> dict:
        prompt = (f"Classify this email to {W.FIRM}'s operations inbox into exactly one category: "
                  f"{', '.join(self.categories)}. Reply with JSON only: "
                  '{"category": "...", "confidence": 0.0-1.0}')
        r = self.ctx.chat([{"role": "system", "content": prompt}, {"role": "user", "content": show(msg)}])
        return parse_json(r["content"])

    def extract(self, msg, category) -> dict:
        prompt = (f"Today is {W.TODAY}; times are UTC. Extract these fields from the email as JSON only, "
                  f"using null when a field is not given: {FIELDS[category]}")
        r = self.ctx.chat([{"role": "system", "content": prompt}, {"role": "user", "content": show(msg)}])
        return parse_json(r["content"])

    def compose(self, msg, facts: str) -> str:
        prompt = (f"You write short, polite email replies for {W.FIRM}. Write only the body of a reply to the "
                  f"email below. It must say: {facts}. Do not promise anything else.")
        r = self.ctx.chat([{"role": "system", "content": prompt}, {"role": "user", "content": show(msg)}])
        return (r["content"] or "").strip()

    # ── fixed steps ──
    def client_for(self, msg, fields) -> dict | None:
        for q in (msg["from"], msg["from"].split("@")[-1], fields.get("client_name")):
            if q and not q.endswith(W.DOMAIN):
                hits = self.tool("find_client", query=q).get("clients", [])
                if hits:
                    return self.tool("read_client", client_id=hits[0]["client_id"])["client"]
        return None

    def reply(self, msg, facts, attachments=()):
        body = self.compose(msg, facts)
        self.tool("draft_reply", to=[self.reply_to(msg)], subject="Re: " + msg["subject"], body=body,
                  attachments=list(attachments), in_reply_to=msg["id"])

    def reply_to(self, msg) -> str:
        return msg["from"]

    def hand_back(self, why):
        return {"status": "handed_back", "reason": why}

    def pick_event(self, client, date):
        evs = [e for e in self.tool("list_events", client_id=client["id"], date_from="2026-03-02")["events"]
               if e["status"] == "scheduled"]
        on_day = [e for e in evs if date and e["start"].startswith(date)]
        return (on_day or evs or [None])[0]

    def run(self, msg) -> dict:
        cat = self.classify(msg).get("category")
        if cat not in FIELDS:
            return self.hand_back(f"category {cat}")
        f = self.extract(msg, cat)
        client = self.client_for(msg, f)
        if cat != "task_request" and not client:
            return self.hand_back("unknown client")
        return getattr(self, cat)(msg, f, client)

    # ── routes ──
    def meeting_request(self, msg, f, client):
        start = W.norm_time(f.get("start"))
        if not start:
            return self.hand_back("no start time")
        self.book(client, start, f.get("minutes") or 60, msg)
        self.reply(msg, f"the meeting is booked for {start} UTC")
        return {"status": "done"}

    def book(self, client, start, minutes, msg):
        return self.tool("create_event", title=f"Meeting with {client['name']}", start=start, minutes=int(minutes),
                         client_id=client["id"], attendees=[self.reply_to(msg)])

    def reschedule_meeting(self, msg, f, client):
        start = W.norm_time(f.get("new_start"))
        ev = self.pick_event(client, f.get("original_date"))
        if not start or not ev:
            return self.hand_back("no new time or no meeting to move")
        self.tool("move_event", event_id=ev["id"], start=start)
        self.reply(msg, f"'{ev['title']}' is moved to {start} UTC")
        return {"status": "done"}

    def cancel_meeting(self, msg, f, client):
        ev = self.pick_event(client, f.get("date"))
        if not ev:
            return self.hand_back("no meeting to cancel")
        self.tool("cancel_event", event_id=ev["id"], note="Cancelled at the client's request.")
        self.reply(msg, f"'{ev['title']}' on {ev['start']} UTC is cancelled")
        return {"status": "done"}

    def invoice_request(self, msg, f, client):
        period = f.get("period") or "2026-02"
        out = self.tool("create_invoice", client_id=client["id"], period=period)
        if "error" in out:
            return self.hand_back(out["error"])
        inv = out["invoice"]
        self.reply(msg, f"invoice {inv['id']} for {period}, total ${inv['total_cents'] / 100:,.2f}, is attached",
                   [inv["id"]])
        return {"status": "done"}

    def document_request(self, msg, f, client):
        docs = self.tool("find_documents", query=f.get("document") or "", client_id=client["id"])["documents"]
        if not docs:
            return self.hand_back("document not found")
        self.reply(msg, f"'{docs[0]['title']}' is attached", [docs[0]["id"]])
        return {"status": "done"}

    def task_request(self, msg, f, client):
        out = self.tool("create_task", title=f.get("title") or msg["subject"], owner=f.get("owner") or "",
                        client_id=client["id"] if client else None, due=f.get("due"))
        if "error" in out:
            return self.hand_back(out["error"])
        return {"status": "done"}
