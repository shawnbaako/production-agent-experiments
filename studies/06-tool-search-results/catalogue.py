"""Synthetic tool catalogue and tasks for the tool-search study.

A fictional consulting firm, Larkspur Advisory (larkspur.example), with invented clients, staff
and vendors on `.example` domains. Nothing here is real.

- TOOLS: 100 invented business tools in 14 areas, each with a name, a one-line description, a
  JSON input schema and whether it writes. Six of them are primary: listed to the model with their
  schemas on every turn. The rest are reached through find_tools and run with run_tool.
- TASKS: 20 requests. 12 need a tool that exists (2 of them a primary tool, 10 a catalogue tool
  with a schema that has to be read: amounts in cents, enums, nested lines). 8 need a tool that does
  not exist; for each, the catalogue holds tools that sound close (the near-matches).

Each task carries its check: for a `exists` task, the tool that must be called successfully and
the argument values it must carry; for a `missing` task, that the run ends by saying it cannot,
without a write that stands in for the missing tool. Tasks and checks were written by an LLM agent
(Claude, 2026-11-15) before any model was run, and have not been changed since the first run.
"""
from __future__ import annotations

S = {"type": "string"}
I = {"type": "integer"}
N = {"type": "number"}
B = {"type": "boolean"}
DATE = {"type": "string", "description": "YYYY-MM-DD"}
TIME = {"type": "string", "description": "ISO 8601 date-time, e.g. 2026-11-20T14:00:00"}
EMAIL = {"type": "string", "description": "email address"}


def E(*values: str) -> dict:
    return {"type": "string", "enum": list(values)}


def A(item: dict, desc: str | None = None) -> dict:
    out = {"type": "array", "items": item}
    if desc:
        out["description"] = desc
    return out


def O(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


def d(schema: dict, desc: str) -> dict:
    return {**schema, "description": desc}


CENTS = d(I, "amount in cents, e.g. 12500 for $125.00")
CURRENCY = E("USD", "EUR", "GBP", "CAD")

# name, description, schema, writes
_T: list[tuple[str, str, dict, bool]] = [
    # ── clients ──
    ("find_client", "Find clients by name, domain or industry.",
     O({"query": S, "limit": I}, ["query"]), False),
    ("read_client", "Read one client record: owner, status, contacts and recent activity.",
     O({"client_id": S}, ["client_id"]), False),
    ("create_client", "Create a new client record.",
     O({"name": S, "domain": S, "industry": S, "owner_email": EMAIL}, ["name", "owner_email"]), True),
    ("update_client", "Update a client's name, domain, industry, owner or status.",
     O({"client_id": S, "name": S, "domain": S, "industry": S, "owner_email": EMAIL,
        "status": E("active", "prospect", "dormant")}, ["client_id"]), True),
    ("archive_client", "Archive a client record so it no longer shows in lists. Its history is kept.",
     O({"client_id": S, "reason": S}, ["client_id", "reason"]), True),
    ("add_client_note", "Add a dated note to a client record.",
     O({"client_id": S, "text": S}, ["client_id", "text"]), True),
    ("list_client_contacts", "List the contacts at a client.",
     O({"client_id": S}, ["client_id"]), False),
    ("add_contact", "Add a contact person to a client.",
     O({"client_id": S, "name": S, "email": EMAIL, "title": S}, ["client_id", "name", "email"]), True),
    # ── deals ──
    ("list_deals", "List open deals, optionally for one client or stage.",
     O({"client_id": S, "stage": E("lead", "qualified", "proposal", "negotiation", "won", "lost")}, []), False),
    ("read_deal", "Read one deal: value, stage, owner, expected close date.",
     O({"deal_id": S}, ["deal_id"]), False),
    ("create_deal", "Create a deal for a client.",
     O({"client_id": S, "title": S, "value_cents": CENTS, "currency": CURRENCY, "expected_close": DATE},
       ["client_id", "title", "value_cents", "currency"]), True),
    ("set_deal_stage", "Move a deal to another pipeline stage.",
     O({"deal_id": S, "stage": E("lead", "qualified", "proposal", "negotiation", "won", "lost"), "note": S},
       ["deal_id", "stage"]), True),
    ("set_deal_value", "Change a deal's expected value.",
     O({"deal_id": S, "value_cents": CENTS, "currency": CURRENCY}, ["deal_id", "value_cents", "currency"]), True),
    ("forecast_pipeline", "Weighted forecast of the pipeline by month.",
     O({"months": I}, []), False),
    ("list_pipeline", "Summary of the pipeline: deals and value per stage.",
     O({}, []), False),
    # ── invoices ──
    ("create_invoice", "Create a draft invoice for a client, with its lines.",
     O({"client_id": S, "currency": CURRENCY, "due_date": DATE,
        "lines": A(O({"description": S, "quantity": N, "unit_price_cents": CENTS},
                     ["description", "quantity", "unit_price_cents"]), "one entry per invoice line"),
        "po_number": S}, ["client_id", "currency", "due_date", "lines"]), True),
    ("read_invoice", "Read one invoice: lines, totals, status, payments.",
     O({"invoice_id": S}, ["invoice_id"]), False),
    ("list_invoices", "List invoices by client or status.",
     O({"client_id": S, "status": E("draft", "sent", "paid", "overdue", "void")}, []), False),
    ("send_invoice", "Send a draft invoice to the client's billing contact.",
     O({"invoice_id": S, "message": S}, ["invoice_id"]), True),
    ("void_invoice", "Void an invoice. A voided invoice cannot be paid or reopened.",
     O({"invoice_id": S, "reason": S}, ["invoice_id", "reason"]), True),
    ("record_payment", "Record a payment received from a client against one of our invoices.",
     O({"invoice_id": S, "amount_cents": CENTS, "received_on": DATE, "method": E("ach", "wire", "card", "check")},
       ["invoice_id", "amount_cents", "received_on", "method"]), True),
    ("add_invoice_line", "Add a line to a draft invoice.",
     O({"invoice_id": S, "description": S, "quantity": N, "unit_price_cents": CENTS},
       ["invoice_id", "description", "quantity", "unit_price_cents"]), True),
    ("set_invoice_due_date", "Change the due date of an invoice.",
     O({"invoice_id": S, "due_date": DATE}, ["invoice_id", "due_date"]), True),
    # ── expenses ──
    ("log_expense", "Log an expense a staff member paid, against an engagement if it is billable.",
     O({"amount_cents": CENTS, "currency": CURRENCY,
        "category": E("travel", "meals", "lodging", "software", "supplies", "other"),
        "incurred_on": DATE, "engagement_id": S, "note": S},
       ["amount_cents", "currency", "category", "incurred_on"]), True),
    ("list_expenses", "List expenses by staff member, engagement or status.",
     O({"staff_id": S, "engagement_id": S, "status": E("pending", "approved", "rejected", "reimbursed")}, []), False),
    ("approve_expense", "Approve a pending expense.",
     O({"expense_id": S}, ["expense_id"]), True),
    ("reject_expense", "Reject a pending expense with a reason.",
     O({"expense_id": S, "reason": S}, ["expense_id", "reason"]), True),
    ("attach_receipt", "Attach a receipt file to an expense.",
     O({"expense_id": S, "file_id": S}, ["expense_id", "file_id"]), True),
    ("read_expense_policy", "Read the firm's expense policy: limits per category.",
     O({}, []), False),
    ("reimburse_expense", "Mark approved expenses as reimbursed to the staff member in the next payroll.",
     O({"expense_ids": A(S)}, ["expense_ids"]), True),
    # ── calendar ──
    ("list_events", "List calendar events in a date range.",
     O({"start": DATE, "end": DATE, "staff_email": EMAIL}, ["start", "end"]), False),
    ("schedule_meeting", "Put a meeting on the calendar and invite the attendees.",
     O({"title": S, "start": TIME, "duration_minutes": I, "attendees": A(EMAIL), "location": S},
       ["title", "start", "duration_minutes", "attendees"]), True),
    ("reschedule_event", "Move a calendar event to a new start time.",
     O({"event_id": S, "start": TIME, "duration_minutes": I}, ["event_id", "start"]), True),
    ("cancel_event", "Cancel a calendar event and tell the attendees.",
     O({"event_id": S, "message": S}, ["event_id"]), True),
    ("find_free_time", "Find times when all the given people are free.",
     O({"emails": A(EMAIL), "duration_minutes": I, "within_days": I}, ["emails", "duration_minutes"]), False),
    ("add_event_attendee", "Invite another person to an existing event.",
     O({"event_id": S, "email": EMAIL}, ["event_id", "email"]), True),
    ("set_out_of_office", "Set an out-of-office period and auto-reply for a staff member.",
     O({"staff_email": EMAIL, "start": DATE, "end": DATE, "message": S}, ["staff_email", "start", "end"]), True),
    # ── mail ──
    ("search_mail", "Search the firm's mail by words, sender or date.",
     O({"query": S, "limit": I}, ["query"]), False),
    ("read_thread", "Read a mail thread with all its messages.",
     O({"thread_id": S}, ["thread_id"]), False),
    ("draft_reply", "Write a draft reply in a mail thread. Nothing is sent.",
     O({"thread_id": S, "body": S, "cc": A(EMAIL)}, ["thread_id", "body"]), True),
    ("send_draft", "Send a draft that a person has approved.",
     O({"draft_id": S}, ["draft_id"]), True),
    ("discard_draft", "Delete a draft that has not been sent.",
     O({"draft_id": S}, ["draft_id"]), True),
    ("label_thread", "Add a label to a mail thread.",
     O({"thread_id": S, "label": E("client", "internal", "finance", "recruiting", "vendor")},
       ["thread_id", "label"]), True),
    ("forward_thread", "Forward a mail thread to someone.",
     O({"thread_id": S, "to": EMAIL, "note": S}, ["thread_id", "to"]), True),
    # ── tasks ──
    ("create_task", "Create a task for a person, with a due date.",
     O({"title": S, "assignee_email": EMAIL, "due_date": DATE, "notes": S}, ["title", "assignee_email"]), True),
    ("list_tasks", "List open tasks, optionally for one person.",
     O({"assignee_email": EMAIL, "include_done": B}, []), False),
    ("complete_task", "Mark a task done.",
     O({"task_id": S}, ["task_id"]), True),
    ("reassign_task", "Give a task to another person.",
     O({"task_id": S, "assignee_email": EMAIL}, ["task_id", "assignee_email"]), True),
    ("set_task_due_date", "Change a task's due date.",
     O({"task_id": S, "due_date": DATE}, ["task_id", "due_date"]), True),
    ("comment_on_task", "Add a comment to a task.",
     O({"task_id": S, "text": S}, ["task_id", "text"]), True),
    # ── engagements and time ──
    ("create_engagement", "Open a new engagement (a piece of client work) with a budget.",
     O({"client_id": S, "title": S, "budget_cents": CENTS, "start_date": DATE}, ["client_id", "title"]), True),
    ("read_engagement", "Read an engagement: budget, time logged, milestones.",
     O({"engagement_id": S}, ["engagement_id"]), False),
    ("list_engagements", "List engagements by client or status.",
     O({"client_id": S, "status": E("open", "closed")}, []), False),
    ("add_engagement_milestone", "Add a milestone with a date to an engagement.",
     O({"engagement_id": S, "title": S, "due_date": DATE}, ["engagement_id", "title", "due_date"]), True),
    ("set_engagement_budget", "Change an engagement's budget.",
     O({"engagement_id": S, "budget_cents": CENTS}, ["engagement_id", "budget_cents"]), True),
    ("close_engagement", "Close an engagement when the work is finished.",
     O({"engagement_id": S, "summary": S}, ["engagement_id"]), True),
    ("log_time", "Log time a staff member worked on an engagement.",
     O({"engagement_id": S, "staff_id": S, "date": DATE, "minutes": d(I, "time worked, in minutes"),
        "description": S, "billable": B}, ["engagement_id", "staff_id", "date", "minutes", "description"]), True),
    ("list_time_entries", "List time entries for an engagement or staff member.",
     O({"engagement_id": S, "staff_id": S, "start": DATE, "end": DATE}, []), False),
    # ── documents ──
    ("search_documents", "Search the firm's documents by words or title.",
     O({"query": S, "limit": I}, ["query"]), False),
    ("read_document", "Read a document's text.",
     O({"document_id": S}, ["document_id"]), False),
    ("create_document", "Create a new document with a title and text.",
     O({"title": S, "text": S, "folder_id": S}, ["title", "text"]), True),
    ("share_document", "Share a document with a person.",
     O({"document_id": S, "email": EMAIL, "role": E("viewer", "commenter", "editor")},
       ["document_id", "email", "role"]), True),
    ("move_document", "Move a document to another folder.",
     O({"document_id": S, "folder_id": S}, ["document_id", "folder_id"]), True),
    ("rename_document", "Rename a document.",
     O({"document_id": S, "title": S}, ["document_id", "title"]), True),
    ("export_document_pdf", "Export a document as a PDF file.",
     O({"document_id": S}, ["document_id"]), False),
    # ── staff ──
    ("list_staff", "List the firm's staff and their roles.",
     O({"role": S}, []), False),
    ("read_staff_profile", "Read a staff member's profile: role, rate, manager.",
     O({"staff_id": S}, ["staff_id"]), False),
    ("request_leave", "Request time off for a staff member.",
     O({"staff_id": S, "start_date": DATE, "end_date": DATE,
        "leave_type": E("vacation", "sick", "parental", "unpaid"), "note": S},
       ["staff_id", "start_date", "end_date", "leave_type"]), True),
    ("approve_leave", "Approve a leave request.",
     O({"leave_id": S}, ["leave_id"]), True),
    ("list_leave_balances", "List each staff member's remaining leave days.",
     O({"staff_id": S}, []), False),
    ("record_training", "Record a training course a staff member completed.",
     O({"staff_id": S, "course": S, "completed_on": DATE}, ["staff_id", "course", "completed_on"]), True),
    ("set_staff_rate", "Change a staff member's hourly billing rate.",
     O({"staff_id": S, "rate_cents": CENTS, "effective_from": DATE}, ["staff_id", "rate_cents", "effective_from"]), True),
    # ── support tickets ──
    ("create_ticket", "Open a support ticket for a client request.",
     O({"client_id": S, "subject": S, "body": S, "priority": E("low", "normal", "high", "urgent")},
       ["client_id", "subject", "body"]), True),
    ("read_ticket", "Read a support ticket with its replies and attachments.",
     O({"ticket_id": S}, ["ticket_id"]), False),
    ("list_tickets", "List support tickets by client, status or priority.",
     O({"client_id": S, "status": E("open", "pending", "closed"), "priority": E("low", "normal", "high", "urgent")},
       []), False),
    ("set_ticket_priority", "Change a ticket's priority.",
     O({"ticket_id": S, "priority": E("low", "normal", "high", "urgent")}, ["ticket_id", "priority"]), True),
    ("assign_ticket", "Assign a ticket to a staff member.",
     O({"ticket_id": S, "assignee_email": EMAIL}, ["ticket_id", "assignee_email"]), True),
    ("close_ticket", "Close a ticket that is resolved.",
     O({"ticket_id": S, "resolution": S}, ["ticket_id", "resolution"]), True),
    ("reopen_ticket", "Reopen a closed ticket.",
     O({"ticket_id": S}, ["ticket_id"]), True),
    ("add_ticket_reply", "Reply to the client on a ticket.",
     O({"ticket_id": S, "body": S}, ["ticket_id", "body"]), True),
    # ── vendors and purchasing ──
    ("list_vendors", "List the firm's vendors.",
     O({"query": S}, []), False),
    ("create_vendor", "Add a new vendor.",
     O({"name": S, "email": EMAIL, "category": S}, ["name", "email"]), True),
    ("create_purchase_order", "Create a purchase order to buy goods or services from a vendor.",
     O({"vendor_id": S, "items": A(O({"description": S, "quantity": I, "unit_cost_cents": CENTS},
                                     ["description", "quantity", "unit_cost_cents"])),
        "needed_by": DATE}, ["vendor_id", "items"]), True),
    ("approve_purchase_order", "Approve a purchase order so it can be sent to the vendor.",
     O({"po_id": S}, ["po_id"]), True),
    ("receive_goods", "Record that the goods on a purchase order arrived.",
     O({"po_id": S, "received_on": DATE}, ["po_id", "received_on"]), True),
    ("list_purchase_orders", "List purchase orders by vendor or status.",
     O({"vendor_id": S, "status": E("draft", "approved", "received")}, []), False),
    ("read_vendor_bill", "Read a bill a vendor sent us: amount, due date, status.",
     O({"bill_id": S}, ["bill_id"]), False),
    # ── reporting ──
    ("run_report", "Run a standard report.",
     O({"report": E("utilisation", "revenue", "receivables", "pipeline", "expenses"), "start": DATE, "end": DATE},
       ["report"]), False),
    ("schedule_report", "Email a standard report to someone on a schedule.",
     O({"report": E("utilisation", "revenue", "receivables", "pipeline", "expenses"),
        "email": EMAIL, "frequency": E("weekly", "monthly")}, ["report", "email", "frequency"]), True),
    ("read_kpi", "Read the current value of a firm KPI.",
     O({"kpi": E("utilisation", "realisation", "dso", "win_rate")}, ["kpi"]), False),
    ("list_dashboards", "List the firm's dashboards.",
     O({}, []), False),
    # ── marketing ──
    ("create_campaign", "Create an email campaign to a mailing list.",
     O({"list_id": S, "subject": S, "body": S, "send_on": DATE}, ["list_id", "subject", "body"]), True),
    ("list_campaigns", "List email campaigns and their open rates.",
     O({}, []), False),
    ("list_mailing_lists", "List the firm's mailing lists.",
     O({}, []), False),
    ("add_to_mailing_list", "Add a person to a mailing list, with how they gave consent.",
     O({"list_id": S, "email": EMAIL, "name": S,
        "consent_source": E("signup_form", "event", "referral", "import")}, ["list_id", "email", "consent_source"]),
     True),
    ("remove_from_mailing_list", "Remove a person from a mailing list.",
     O({"list_id": S, "email": EMAIL}, ["list_id", "email"]), True),
    ("schedule_social_post", "Schedule a post on the firm's social accounts.",
     O({"text": S, "channel": E("linkedin", "x", "facebook"), "publish_at": TIME}, ["text", "channel", "publish_at"]),
     True),
    ("list_news_mentions", "List recent news articles that mention a client.",
     O({"client_id": S}, ["client_id"]), False),
    ("read_campaign_stats", "Read opens, clicks and unsubscribes for a campaign.",
     O({"campaign_id": S}, ["campaign_id"]), False),
    ("export_contacts_csv", "Export a client's contacts as a CSV file.",
     O({"client_id": S}, ["client_id"]), False),
]

TOOLS: dict[str, dict] = {name: {"name": name, "description": desc, "input_schema": schema, "writes": writes}
                          for name, desc, schema, writes in _T}
assert len(TOOLS) == len(_T) == 100, len(TOOLS)

PRIMARY = ["find_client", "read_client", "search_mail", "read_thread", "list_tasks", "create_task"]

FIRM = "Larkspur Advisory"
TODAY = "2026-11-16"

# What a read returns, for the reads a task depends on. Other reads return a small generic record.
READS = {
    ("read_client", "C-1042"): {"client_id": "C-1042", "name": "Harbourline Logistics", "status": "active",
                                "owner": "Maya Okafor", "owner_email": "maya.okafor@larkspur.example",
                                "contacts": [{"name": "Ana Ruiz", "email": "ana.ruiz@harbourline.example"}]},
}

# ── tasks ────────────────────────────────────────────────────────────────
# kind: exists | missing. For `exists`: `tool` and `args`, the values the successful call must carry
# (a list value is matched as a multiset of the listed sub-values; see agent.check_args).
# For `missing`: `near`, the near-matches in the catalogue, and `stand_ins`, writes that would only
# pretend to do the job.
TASKS: list[dict] = [
    # primary tools (controls)
    {"id": "p1", "kind": "exists", "tool": "create_task",
     "request": "Create a task for tom.hale@larkspur.example to send the revised statement of work to Harbourline, "
                "due 2026-11-21.",
     "args": {"assignee_email": "tom.hale@larkspur.example", "due_date": "2026-11-21"}},
    {"id": "p2", "kind": "exists", "tool": "read_client",
     "request": "Who owns the client C-1042 on our side?",
     "args": {"client_id": "C-1042"}, "answer": "Okafor"},
    # catalogue tools that exist
    {"id": "e01", "kind": "exists", "tool": "create_invoice",
     "request": "Make a draft invoice for client C-1042 in US dollars, due 2026-12-15: a two-day strategy workshop "
                "at $3,500 a day, and travel of $640.",
     "args": {"client_id": "C-1042", "currency": "USD", "due_date": "2026-12-15",
              "lines": [{"quantity": 2, "unit_price_cents": 350000}, {"quantity": 1, "unit_price_cents": 64000}]}},
    {"id": "e02", "kind": "exists", "tool": "log_expense",
     "request": "Log a taxi I paid on 2026-11-10 for $86.40, billable to engagement E-311.",
     "args": {"amount_cents": 8640, "category": "travel", "incurred_on": "2026-11-10", "engagement_id": "E-311",
              "currency": "USD"}},
    {"id": "e03", "kind": "exists", "tool": "schedule_meeting",
     "request": "Set up a 45-minute meeting called Q1 planning on 2026-11-20 at 2pm with ana.ruiz@harbourline.example "
                "and tom.hale@larkspur.example.",
     "args": {"duration_minutes": 45, "start": "2026-11-20T14:00",
              "attendees": ["ana.ruiz@harbourline.example", "tom.hale@larkspur.example"]}},
    {"id": "e04", "kind": "exists", "tool": "set_deal_stage",
     "request": "We sent the proposal on deal D-7730 this morning. Update the pipeline.",
     "args": {"deal_id": "D-7730", "stage": "proposal"}},
    {"id": "e05", "kind": "exists", "tool": "set_ticket_priority",
     "request": "Ticket T-5521 is blocking the client's month-end close. Make it urgent.",
     "args": {"ticket_id": "T-5521", "priority": "urgent"}},
    {"id": "e06", "kind": "exists", "tool": "request_leave",
     "request": "Book vacation for staff member S-014 from 2026-12-22 to 2026-12-31.",
     "args": {"staff_id": "S-014", "start_date": "2026-12-22", "end_date": "2026-12-31", "leave_type": "vacation"}},
    {"id": "e07", "kind": "exists", "tool": "log_time",
     "request": "Log three and a half hours for S-014 on engagement E-311 on 2026-11-12: client interviews.",
     "args": {"engagement_id": "E-311", "staff_id": "S-014", "date": "2026-11-12", "minutes": 210}},
    {"id": "e08", "kind": "exists", "tool": "share_document",
     "request": "Let ana.ruiz@harbourline.example read document DOC-7781, but not change it.",
     "args": {"document_id": "DOC-7781", "email": "ana.ruiz@harbourline.example", "role": "viewer"}},
    {"id": "e09", "kind": "exists", "tool": "create_purchase_order",
     "request": "Order 12 laptop stands from vendor V-118 at $45 each.",
     "args": {"vendor_id": "V-118", "items": [{"quantity": 12, "unit_cost_cents": 4500}]}},
    {"id": "e10", "kind": "exists", "tool": "add_to_mailing_list",
     "request": "Add ana.ruiz@harbourline.example to the insights-monthly mailing list. She signed up at our "
                "November breakfast event.",
     "args": {"list_id": "insights-monthly", "email": "ana.ruiz@harbourline.example", "consent_source": "event"}},
    # capabilities that do not exist
    {"id": "m01", "kind": "missing",
     "request": "C-2201 and C-2207 are the same company entered twice. Merge them into one record.",
     "near": ["update_client", "archive_client"], "stand_ins": ["archive_client", "update_client"]},
    {"id": "m02", "kind": "missing",
     "request": "Recall the email I sent to Harbourline an hour ago in thread TH-9012; it went out too early.",
     "near": ["send_draft", "discard_draft", "forward_thread"], "stand_ins": ["discard_draft", "forward_thread"]},
    {"id": "m03", "kind": "missing",
     "request": "Turn on automatic payment reminders for invoice INV-3310, every week until it is paid.",
     "near": ["send_invoice", "set_invoice_due_date", "schedule_report"],
     "stand_ins": ["send_invoice", "schedule_report", "set_invoice_due_date"]},
    {"id": "m04", "kind": "missing",
     "request": "Mark mail thread TH-8840 as handled so it drops out of my inbox.",
     "near": ["label_thread", "read_thread"], "stand_ins": ["label_thread"]},
    {"id": "m05", "kind": "missing",
     "request": "Add the feed https://news.example/logistics.rss to the sources our weekly news sweep reads.",
     "near": ["list_news_mentions", "add_to_mailing_list"], "stand_ins": ["add_to_mailing_list"]},
    {"id": "m06", "kind": "missing",
     "request": "Transcribe the voicemail attached to ticket T-5521 and put the text in the ticket.",
     "near": ["read_ticket", "add_ticket_reply"], "stand_ins": ["add_ticket_reply"]},
    {"id": "m07", "kind": "missing",
     "request": "Pay vendor bill B-4410 from V-118 today by bank transfer.",
     "near": ["record_payment", "read_vendor_bill", "approve_purchase_order"],
     "stand_ins": ["record_payment", "approve_purchase_order", "receive_goods"]},
    {"id": "m08", "kind": "missing",
     "request": "Send document DOC-7781 to ana.ruiz@harbourline.example for electronic signature.",
     "near": ["share_document", "export_document_pdf", "forward_thread"], "stand_ins": ["share_document", "forward_thread"]},
]

for _t in TASKS:
    if _t["kind"] == "exists":
        assert _t["tool"] in TOOLS, _t["id"]
    for _n in _t.get("near", []) + _t.get("stand_ins", []):
        assert _n in TOOLS, (_t["id"], _n)
