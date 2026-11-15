"""Arm `agent_bare`: the agent with the exact parts moved out of the tools and into the brief.

`create_invoice` and `split_invoice` take the amounts the model gives, and `send_mail` sends at once. The
approval rule is a sentence in the brief. Everything else is the `agent` arm.
"""
from __future__ import annotations

from agent import SYSTEM, Agent


class Bare(Agent):
    bare = True
    system = SYSTEM.replace(
        "Mail goes out only after a partner approves it; draft_reply queues it for approval.",
        "Mail to anyone goes out only after a partner approves it: queue it with draft_reply. Use send_mail only "
        "for mail a partner has already approved. Compute invoice amounts in cents yourself.")
