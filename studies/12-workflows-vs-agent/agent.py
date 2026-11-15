"""Arm `agent`: one tool-calling loop over the same tools, with the message and a short brief.

The exact parts stay in the tools (world.py): invoice amounts are computed in cents, and mail can only be
queued for a partner's approval. Nothing else is decided in code.
"""
from __future__ import annotations

import json

import world as W

MAX_STEPS = 20

SYSTEM = f"""You are the operations assistant for {W.FIRM}, a small consulting firm ({W.DOMAIN}). Today is \
{W.TODAY}; all times are UTC. A message has arrived in the firm's operations inbox. Handle it for the firm \
with the tools: look things up instead of guessing, and do what the message needs. Mail goes out only after \
a partner approves it; draft_reply queues it for approval.
When you are finished, write a one-line note for the firm's staff that starts DONE: with what you did, or \
NEEDS PERSON: if someone in the firm has to handle it."""


def show(msg: dict) -> str:
    return f"New message {msg['id']}\nFrom: {msg['from']}\nSubject: {msg['subject']}\n\n{msg['body']}"


class Agent:
    system = SYSTEM
    bare = False

    def __init__(self, ctx, w: dict):
        self.ctx, self.w, self.log = ctx, w, []

    def schemas(self):
        return W.BARE_SCHEMAS if self.bare else W.SCHEMAS

    def tool(self, name, raw):
        out = W.call_tool(self.w, name, raw, bare=self.bare)
        self.log.append({"tool": name, "args": raw, "ok": "error" not in out})
        return out

    def run(self, msg) -> dict:
        messages = [{"role": "system", "content": self.system}, {"role": "user", "content": show(msg)}]
        for _ in range(MAX_STEPS):
            r = self.ctx.chat(messages, self.schemas())
            calls = r["tool_calls"]
            ids = [c["id"] or f"call_{len(messages)}_{i}" for i, c in enumerate(calls)]
            messages.append({"role": "assistant", "content": r["content"] or "", **({"tool_calls": [
                {"id": i, "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
                for i, c in zip(ids, calls)]} if calls else {})})
            if not calls:
                note = (r["content"] or "").strip()
                return {"status": "handed_back" if "NEEDS PERSON" in note.upper() else "done", "note": note}
            for i, c in zip(ids, calls):
                messages.append({"role": "tool", "tool_call_id": i,
                                 "content": json.dumps(self.tool(c["name"], c["arguments"]))})
        return {"status": "cut_off", "note": ""}
