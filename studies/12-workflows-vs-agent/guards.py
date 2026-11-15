"""Arm `guards`: the workflow plus the patches workflows usually grow.

Each patch answers a failure a workflow author meets in the first weeks:
- a `no_action` category, so thank-you mails are not handed back;
- a confidence floor: below 0.6 the message is handed back;
- forwarded mail: the original sender in a staff forward is the client and the one to answer;
- dedupe: no second invoice for a client and month (answer with the existing one); no event booked where
  the client already has one at that time;
- a clash check: a booking or move that overlaps the owner's calendar is handed back;
- a missing-field fallback: no time, no move target, no document: hand back (the base already does);
- a cap: one write per message.
Written with the base workflow, before any model was run.
"""
from __future__ import annotations

import re

import world as W
from workflow import CATEGORIES, Workflow

FWD = re.compile(r"Forwarded message.*?From:[^<\n]*<([^>]+)>", re.S | re.I)


class Guarded(Workflow):
    categories = CATEGORIES[:-1] + ["no_action", "other"]

    def __init__(self, ctx, w):
        super().__init__(ctx, w)
        self.writes = 0

    def tool(self, name, **args):
        if name in ("create_event", "move_event", "cancel_event", "create_invoice", "create_task"):
            if self.writes >= 1:
                return {"error": "cap: one write per message"}
            self.writes += 1
        return super().tool(name, **args)

    def run(self, msg) -> dict:
        c = self.classify(msg)
        if c.get("category") == "no_action":
            return {"status": "done"}
        try:
            conf = float(c.get("confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0
        if conf < 0.6:
            return self.hand_back(f"low confidence {conf}")
        if c.get("category") not in self.categories[:-2]:
            return self.hand_back(f"category {c.get('category')}")
        f = self.extract(msg, c["category"])
        client = self.client_for(msg, f)
        if c["category"] != "task_request" and not client:
            return self.hand_back("unknown client")
        return getattr(self, c["category"])(msg, f, client)

    def forwarded_from(self, msg) -> str | None:
        m = FWD.search(msg["body"])
        return m.group(1).strip().lower() if m and msg["from"].endswith(W.DOMAIN) else None

    def reply_to(self, msg) -> str:
        return self.forwarded_from(msg) or msg["from"]

    def client_for(self, msg, fields):
        fwd = self.forwarded_from(msg)
        if fwd:
            hits = self.tool("find_client", query=fwd).get("clients", [])
            if hits:
                return self.tool("read_client", client_id=hits[0]["client_id"])["client"]
        return super().client_for(msg, fields)

    def clashes(self, client, start, minutes, skip=None):
        return W.overlaps(self.w, client["owner"], start, int(minutes), skip=skip)

    def meeting_request(self, msg, f, client):
        start = W.norm_time(f.get("start"))
        if start:
            same = [e for e in self.tool("list_events", client_id=client["id"])["events"]
                    if e["status"] == "scheduled" and e["start"] == start]
            if same:
                self.reply(msg, f"the meeting at {start} UTC is already booked")
                return {"status": "done"}
            if self.clashes(client, start, f.get("minutes") or 60):
                return self.hand_back("time clashes with the owner's calendar")
        return super().meeting_request(msg, f, client)

    def reschedule_meeting(self, msg, f, client):
        start = W.norm_time(f.get("new_start"))
        ev = self.pick_event(client, f.get("original_date"))
        if start and ev and self.clashes(client, start, ev["minutes"], skip=ev["id"]):
            return self.hand_back("new time clashes with the owner's calendar")
        return super().reschedule_meeting(msg, f, client)

    def invoice_request(self, msg, f, client):
        period = f.get("period") or "2026-02"
        have = [i for i in self.tool("list_invoices", client_id=client["id"])["invoices"]
                if i["period"] == period and i["status"] != "void"]
        if have:
            self.reply(msg, f"invoice {have[0]['id']} for {period} was issued on {have[0]['issued']}; "
                            "it is attached again", [have[0]["id"]])
            return {"status": "done"}
        return super().invoice_request(msg, f, client)
