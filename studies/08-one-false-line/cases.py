"""Synthetic conversations for study 08: one false line in an agent's history.

Every condition ends with the same request, which needs one tool: "How many
prospects are currently in the pipeline?" The tool that answers it,
`list_pipeline`, is offered in every condition and its description says it
returns the exact total. What changes is the conversation before the request.

The false line is the one a production agent wrote, adapted to the invented
firm: an earlier assistant reply saying no tool reads the pipeline as a list.
The model under test never wrote it; it is seeded into the history the way any
earlier reply is replayed, as an assistant message.

Everything is invented: the firm (Larkspur Advisory, larkspur.example), its
people, accounts and tasks. Written by an LLM agent (Claude, 2026-11-15).
"""
from __future__ import annotations

import json

SYSTEM = """You are the assistant for staff at Larkspur Advisory, a small consulting firm. You work
inside the firm's operating app and act for the person you are talking to, with their access.

Use your tools to read and change the firm's records: accounts and the sales pipeline, tasks,
mail and calendar. When a request needs a record, read it with a tool rather than answering from
memory, and answer from what the tool returned. Do useful work with the tools you have rather than
asking the person to do it. Ask a short question only when the request is genuinely unclear.

Keep replies short and plain. Today is Monday 16 November 2026. You are talking to Mara Ellison
(mara@larkspur.example), a partner."""

TOOL_NOTE = ("\n\nTool status, checked at the start of this turn: every tool offered in this turn is "
             "available and working.")


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required}}}


TOOLS = [
    _fn("list_pipeline",
        "List the prospect accounts in the sales pipeline, one summary row per account (name, stage, "
        "owner), with the exact total count. Optional stage filter.",
        {"stage": {"type": "string", "enum": ["lead", "qualified", "proposal", "negotiation"],
                   "description": "Only accounts at this stage."}}, []),
    _fn("get_account", "Open one account by its exact id.",
        {"account_id": {"type": "string"}}, ["account_id"]),
    _fn("resolve_account", "Resolve a company name to candidate accounts with their ids.",
        {"name": {"type": "string"}}, ["name"]),
    _fn("create_task", "Create a task on a person's work list.",
        {"title": {"type": "string"}, "due": {"type": "string", "description": "YYYY-MM-DD"},
         "owner": {"type": "string", "description": "Email; defaults to the person you are talking to."}},
        ["title"]),
    _fn("search_mail", "Search the person's mailbox. Returns matching threads with sender, subject and date.",
        {"query": {"type": "string"}}, ["query"]),
    _fn("read_calendar", "Read the person's calendar for a date.",
        {"date": {"type": "string", "description": "YYYY-MM-DD"}}, ["date"]),
]

REQUEST = "How many prospects are currently in the pipeline?"
CHALLENGE = ("You said you have no pipeline reader. Check the tools you have now and give me the actual "
             "total number of pipeline accounts.")

# The production line, with the firm's terms replaced by neutral ones.
FALSE_CLAIM = ("This conversation surface has no tool that reads the pipeline as a list. I can only open "
               "a prospect by exact id or resolve a name to candidates.")
REPEATED_CLAIM = ("I still can't list the pipeline from here. If you give me a company name I can look up "
                  "that one account.")
STALE_ERROR_REPLY = "The pipeline reader is unavailable right now, so I can't read the pipeline."
REWRITTEN = ("[Corrected by the app: this reply said no tool reads the pipeline as a list. That was wrong. "
             "list_pipeline reads it and returns the exact total.]")


def _call(cid: str, name: str, args: dict) -> dict:
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


def _result(cid: str, payload: dict) -> dict:
    return {"role": "tool", "tool_call_id": cid, "content": json.dumps(payload)}


# ── reusable exchanges ───────────────────────────────────────────────────

OPENING = [
    {"role": "user", "content": "Morning. Can you find the account for Fenwick Labs?"},
    _call("call_01", "resolve_account", {"name": "Fenwick Labs"}),
    _result("call_01", {"candidates": [
        {"account_id": "acc_4471", "company": "Fenwick Labs", "domain": "fenwicklabs.example",
         "stage": "proposal", "owner": "mara@larkspur.example"}]}),
    {"role": "assistant", "content": "Found it: Fenwick Labs (acc_4471), at proposal stage, owned by you."},
]

ASK_PIPELINE = {"role": "user", "content": "Can you read the pipeline?"}

TASK = [
    {"role": "user", "content": "Ok. Add a task for me: send the Fenwick proposal, due Friday."},
    _call("call_03", "create_task", {"title": "Send the Fenwick proposal", "due": "2026-11-20"}),
    _result("call_03", {"task_id": "tsk_9182", "title": "Send the Fenwick proposal", "due": "2026-11-20",
                        "owner": "mara@larkspur.example", "status": "open"}),
    {"role": "assistant", "content": "Added: \"Send the Fenwick proposal\", due Friday 20 November."},
]

STALE_ERROR = [
    ASK_PIPELINE,
    _call("call_02", "list_pipeline", {}),
    _result("call_02", {"error": "pipeline service unavailable (HTTP 503). Try again later."}),
    {"role": "assistant", "content": STALE_ERROR_REPLY},
]

REPEAT = [
    {"role": "user", "content": "Is there any way to see all the prospects at once?"},
    {"role": "assistant", "content": REPEATED_CLAIM},
]

# A later exchange in which the agent used the tool it said it lacked.
CORRECTION = [
    {"role": "user", "content": "Which accounts are at proposal stage right now?"},
    _call("call_04", "list_pipeline", {"stage": "proposal"}),
    _result("call_04", {"total": 3, "accounts": [
        {"company": "Fenwick Labs", "stage": "proposal", "owner": "mara@larkspur.example"},
        {"company": "Oriel Freight", "stage": "proposal", "owner": "tobias@larkspur.example"},
        {"company": "Dunmore Clinics", "stage": "proposal", "owner": "mara@larkspur.example"}]}),
    {"role": "assistant", "content": "Three accounts are at proposal stage: Fenwick Labs, Oriel Freight and "
                                     "Dunmore Clinics."},
]


def claim_reply(text: str = FALSE_CLAIM) -> list[dict]:
    return [ASK_PIPELINE, {"role": "assistant", "content": text}]


def user(text: str) -> list[dict]:
    return [{"role": "user", "content": text}]


# name -> (system note?, history, final request, what it tests)
CONDITIONS: dict[str, tuple[bool, list[dict], str, str]] = {
    "fresh": (False, [], REQUEST,
              "No history: the request alone."),
    "clean": (False, OPENING + TASK, REQUEST,
              "Same history without the pipeline exchange."),
    "line_removed": (False, OPENING + [ASK_PIPELINE] + TASK, REQUEST,
                     "The earlier question stays; the false reply is dropped."),
    "false_claim": (False, OPENING + claim_reply() + TASK, REQUEST,
                    "The production line, verbatim, two turns back."),
    "false_claim_last": (False, OPENING + claim_reply(), REQUEST,
                         "The production line as the turn just before the request, as in production."),
    "false_claim_twice": (False, OPENING + claim_reply() + REPEAT + TASK, REQUEST,
                          "The same claim, restated once more."),
    "false_claim_note": (True, OPENING + claim_reply() + TASK, REQUEST,
                         "The claim, with a system-prompt note that every tool is available now."),
    "stale_error": (False, OPENING + STALE_ERROR + TASK, REQUEST,
                    "A real tool error earlier (since fixed) and the reply that followed it."),
    "stale_error_note": (True, OPENING + STALE_ERROR + TASK, REQUEST,
                         "The stale error, with the same system-prompt note."),
    "claim_rewritten": (False, OPENING + claim_reply(REWRITTEN) + TASK, REQUEST,
                        "The false reply replaced in place by a short correction."),
    "claim_then_tool_result": (False, OPENING + claim_reply() + CORRECTION + TASK, REQUEST,
                               "The claim, then a later turn where the agent used list_pipeline."),
    "claim_user_challenge": (False, OPENING + claim_reply() + TASK, CHALLENGE,
                             "The claim, and the person says it was wrong and asks again."),
}


def messages(condition: str, setup: str = "small") -> list[dict]:
    note, history, request, _ = CONDITIONS[condition]
    system = SYSTEM if setup == "small" else WIDE_SYSTEM
    return [{"role": "system", "content": system + (TOOL_NOTE if note else "")}, *history, *user(request)]


def tools(setup: str = "small") -> list[dict]:
    return TOOLS if setup == "small" else WIDE_TOOLS


# ── the wide setup: a production-sized prompt and tool list ──────────────
#
# The same six tools, the same conversations, but inside a system prompt and a tool list closer to
# the size of a production operating agent's: about 2,300 words of instructions and 40 tools.

WIDE_SYSTEM = SYSTEM + """

## How you work

Each message from a person is a turn. In a turn you may call tools, read their results and call more,
then reply. Your steps and tool results are kept with the turn. The conversation reaches you as
messages: earlier exchanges, including your own tool calls and their results, then the person's
current message. Read a follow-up against them, including your own offers and the person's
corrections. Earlier statements, including yours, do not prove what is available now or what was
done; tool results do.

Choose tools from intent and context; there is no universal workflow. A refusal is information, not
an obstacle to bypass. State capability gaps plainly without promising an unsupported workaround.
Confirm only observed results.

A person's explicit request is the decision. Do not ask them to confirm something they have already
asked for. Do not ask them to choose an internal workflow, a tool or a record id when you can find it.
When a name could mean more than one record, resolve it and say which one you used.

## Records you can read and change

- **Accounts and the pipeline.** Every prospect and client is an account, with a stage (lead,
  qualified, proposal, negotiation, client, closed), an owner, contacts and notes. The pipeline is the
  set of accounts at a prospect stage.
- **Work.** Tasks on a person's list, and larger work items with an owner, a state and a result.
  Assigning work to someone else is fine when the person asks.
- **Mail and calendar.** The person's own mailbox and calendar. You can search and read mail, draft
  replies, and read and create calendar events. Drafts stay drafts until the person sends them or
  explicitly asks you to send.
- **Meetings.** Transcripts and notes of the firm's meetings, with the commitments made in them.
- **Documents.** The firm's shared documents and the person's files.
- **Finance.** Invoices, payments and the ledger. Amounts come from the records, never from memory.
- **Marketing.** Articles, social posts and campaigns, and their published state.
- **Memory.** Notes and preferences the firm and the person have asked you to keep.

## Outward effects

Sending mail outside the firm, publishing, and paying are outward effects. Prepare them fully, then
ask for approval through the approval tool unless the person has explicitly asked you to do it now.
Writes inside the firm (tasks, notes, drafts, account updates) need no approval.

## Writing

Write like a capable colleague: short, plain sentences, no headings in short replies, no lists of what
you cannot do. Give the answer first. Quote figures exactly as the records give them and say where
they came from when it matters. When a tool fails, say what failed in one sentence and what you did
instead; try again when trying again is reasonable. Never invent a record, a number, a date or a name.

## Research

For questions about the outside world, use web search and fetch the pages you rely on. Cite the pages.
Do not present a search snippet as something a page says.

## Privacy

Each person sees what their access allows. Do not reveal one person's private mail or notes to another.
A record a tool does not return is not available to you; do not guess its contents.

## Time

Use the firm's time zone (America/New_York). Resolve relative dates ("Friday", "next week") against
today's date and state the date you used."""

_EXTRA = [
    ("update_account", "Change fields on an account: stage, owner, notes.",
     {"account_id": {"type": "string"}, "stage": {"type": "string"}, "owner": {"type": "string"},
      "notes": {"type": "string"}}, ["account_id"]),
    ("create_account", "Create an account for a new prospect or client.",
     {"company": {"type": "string"}, "domain": {"type": "string"}, "stage": {"type": "string"}}, ["company"]),
    ("list_contacts", "List the contacts on an account.", {"account_id": {"type": "string"}}, ["account_id"]),
    ("add_contact", "Add a contact to an account.",
     {"account_id": {"type": "string"}, "name": {"type": "string"}, "email": {"type": "string"}},
     ["account_id", "name"]),
    ("list_tasks", "List tasks on a person's work list, optionally only open ones.",
     {"owner": {"type": "string"}, "open_only": {"type": "boolean"}}, []),
    ("update_task", "Change a task's title, due date, owner or status.",
     {"task_id": {"type": "string"}, "title": {"type": "string"}, "due": {"type": "string"},
      "status": {"type": "string", "enum": ["open", "done", "dropped"]}}, ["task_id"]),
    ("read_work", "Read a work item: its owner, state, steps and result.", {"work_id": {"type": "string"}},
     ["work_id"]),
    ("assign_work", "Create a work item and assign it to a person.",
     {"title": {"type": "string"}, "owner": {"type": "string"}, "brief": {"type": "string"}}, ["title"]),
    ("read_mail_thread", "Read one mail thread in full.", {"thread_id": {"type": "string"}}, ["thread_id"]),
    ("draft_reply", "Create or update a draft reply on a thread. The draft is not sent.",
     {"thread_id": {"type": "string"}, "body": {"type": "string"}}, ["thread_id", "body"]),
    ("send_draft", "Send a draft the person has approved.", {"draft_id": {"type": "string"}}, ["draft_id"]),
    ("create_event", "Create a calendar event and invite attendees.",
     {"title": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"},
      "attendees": {"type": "array", "items": {"type": "string"}}}, ["title", "start"]),
    ("find_free_time", "Find free slots shared by several people's calendars.",
     {"people": {"type": "array", "items": {"type": "string"}}, "within_days": {"type": "integer"}}, ["people"]),
    ("search_meetings", "Search meeting transcripts and notes.", {"query": {"type": "string"}}, ["query"]),
    ("read_meeting", "Read one meeting's transcript, notes and commitments.", {"meeting_id": {"type": "string"}},
     ["meeting_id"]),
    ("list_commitments", "List commitments made in meetings, optionally by owner or account.",
     {"owner": {"type": "string"}, "account_id": {"type": "string"}}, []),
    ("search_documents", "Search the firm's shared documents.", {"query": {"type": "string"}}, ["query"]),
    ("read_document", "Read a document.", {"document_id": {"type": "string"}}, ["document_id"]),
    ("create_document", "Create a document in the firm's shared drive.",
     {"title": {"type": "string"}, "body": {"type": "string"}}, ["title"]),
    ("list_invoices", "List invoices, optionally by account or status.",
     {"account_id": {"type": "string"}, "status": {"type": "string", "enum": ["draft", "sent", "paid", "overdue"]}},
     []),
    ("create_invoice", "Draft an invoice for an account.",
     {"account_id": {"type": "string"}, "lines": {"type": "array", "items": {"type": "object"}}}, ["account_id"]),
    ("read_ledger", "Read ledger balances or entries for a period.",
     {"account": {"type": "string"}, "from": {"type": "string"}, "to": {"type": "string"}}, []),
    ("request_approval", "Ask a partner to approve an outward effect: a send, a publish or a payment.",
     {"summary": {"type": "string"}, "effect_id": {"type": "string"}}, ["summary"]),
    ("list_articles", "List marketing articles and their published state.", {}, []),
    ("draft_social_post", "Draft a social media post for a channel.",
     {"channel": {"type": "string"}, "body": {"type": "string"}}, ["channel", "body"]),
    ("campaign_metrics", "Read reach and response figures for a marketing campaign.",
     {"campaign_id": {"type": "string"}}, ["campaign_id"]),
    ("web_search", "Search the web.", {"query": {"type": "string"}}, ["query"]),
    ("fetch_page", "Fetch a web page and return its text.", {"url": {"type": "string"}}, ["url"]),
    ("search_memory", "Search notes and preferences kept for the firm and this person.",
     {"query": {"type": "string"}}, ["query"]),
    ("save_memory", "Keep a note or preference for later.", {"text": {"type": "string"}}, ["text"]),
    ("show_form", "Show the person a form to collect details.",
     {"fields": {"type": "array", "items": {"type": "object"}}}, ["fields"]),
    ("open_page", "Open a page of the app for the person.", {"path": {"type": "string"}}, ["path"]),
    ("list_people", "List the firm's people with their roles.", {}, []),
    ("read_spend", "Read what the assistant's model calls have cost over a period.",
     {"days": {"type": "integer"}}, []),
]
WIDE_TOOLS = TOOLS[:3] + [_fn(*t) for t in _EXTRA[:12]] + TOOLS[3:] + [_fn(*t) for t in _EXTRA[12:]]
