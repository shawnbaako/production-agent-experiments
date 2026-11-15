"""Arm `agent_machinery`: the agent with the machinery commonly bolted around one.

- a cap of 8 tool calls per message, after which the run stops and the message goes to a person;
- a repeat guard: a call identical to an earlier one is refused;
- a duplicate-action guard: each writing tool may be used once per message;
- a scope rule in the brief: routine requests only, anything else or anything unclear to a person.
Everything else is the `agent` arm.
"""
from __future__ import annotations

import json

from agent import SYSTEM, Agent

CAP = 8
WRITES = {"create_event", "move_event", "cancel_event", "create_task", "update_task", "create_invoice",
          "split_invoice", "draft_reply", "create_client", "update_client"}


class Machinery(Agent):
    system = SYSTEM + """
Handle routine requests only: booking, moving or cancelling a meeting, an invoice, a document, a task. If the \
message is anything else, or anything is unclear, do not guess: reply NEEDS PERSON: with the reason."""

    def __init__(self, ctx, w):
        super().__init__(ctx, w)
        self.seen, self.used, self.capped = set(), set(), False

    def tool(self, name, raw):
        try:
            key = name + json.dumps(json.loads(raw or "{}"), sort_keys=True)
        except json.JSONDecodeError:
            key = name + raw
        if len(self.log) >= CAP:
            self.capped = True
            return {"error": f"Tool call limit of {CAP} reached. Stop and hand this message to a person."}
        if key in self.seen:
            return {"error": "Refused: this exact call was already made. Use the earlier result."}
        if name in WRITES and name in self.used:
            return {"error": f"Refused: {name} may be used once per message, to prevent duplicate actions."}
        self.seen.add(key)
        if name in WRITES:
            self.used.add(name)
        return super().tool(name, raw)

    def run(self, msg):
        out = super().run(msg)
        if self.capped:
            out["status"] = "handed_back"
        return out
