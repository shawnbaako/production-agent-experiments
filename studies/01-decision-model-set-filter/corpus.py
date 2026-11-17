"""Synthetic corpus for the `sift` study: one yes-no question asked of every item in a large set.

A fictional consulting firm, Larkspur Advisory (larkspur.example), with invented
clients, prospects and people on `.example` domains. Nothing here is real. Three sets:

- MAIL: about 1,500 thread-like items. Background threads come from templates
  (scheduling, invoices, workshops, recruiting, vendors, newsletters ...). Planted
  items are hand-written: positives phrased the way people write (often without
  the obvious keyword) and hard negatives that share the keywords or the topic
  (near-misses) or state the opposite (negations).
- PROMISES: 600 open promises the firm made, and three new client emails; for each
  email a handful of promises are affected (changed, delayed, cancelled, fulfilled)
  and a handful are near-misses (same client, other topic; same topic, other client).
- ACCOUNTS: about 800 prospect descriptions, with planted clinical-lab operators and
  near-misses (lab suppliers, research labs, clinics that send tests out).

Reference labels are the generator's intent: each planted item was written to be a
positive, a near-miss or a negation for a named question (2026-10-18), and has not
been independently relabelled. Every item has a stable id and
a split (`dev` or `held`), assigned by the seed before any model was asked. The
question wordings and their rewordings below were frozen before the first held-out run.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

SEED = 20261018

FIRM = "Larkspur Advisory"
US = ["morgan@larkspur.example", "jordan@larkspur.example"]

CLIENTS = [
    ("Harbor Freight Lines", "harborfl.example"), ("Maple Ridge Health", "mapleridge.example"),
    ("Cobalt Credit Union", "cobaltcu.example"), ("Fenwick Tooling", "fenwick.example"),
    ("Juniper County Schools", "juniperk12.example"), ("Ostrander Foods", "ostrander.example"),
    ("Pellucid Software", "pellucid.example"), ("Quarry Hill Bank", "quarryhill.example"),
    ("Redwater Utilities", "redwater.example"), ("Sable Logistics", "sablelog.example"),
    ("Tamarack Insurance", "tamarack.example"), ("Union Mill Textiles", "unionmill.example"),
    ("Verity Legal Aid", "verity.example"), ("Wexford Hotels", "wexford.example"),
    ("Yarrow Community Foundation", "yarrow.example"), ("Zephyr Aerospace Parts", "zephyrap.example"),
    ("Alder Grove Senior Living", "aldergrove.example"), ("Birchwood Dental Group", "birchwood.example"),
    ("Cascade Water Works", "cascadeww.example"), ("Dunmore Plastics", "dunmore.example"),
    ("Elmstead Realty", "elmstead.example"), ("Foxglove Media", "foxglove.example"),
    ("Granite Peak Outfitters", "granitepeak.example"), ("Hollis & Reed Architects", "hollisreed.example"),
    ("Ironbridge Manufacturing", "ironbridge.example"), ("Keel Marine Services", "keelmarine.example"),
]
FIRST = ["Dana", "Priya", "Marcus", "Elena", "Tom", "Aisha", "Ben", "Chloe", "Diego", "Fatima",
         "Grace", "Hiro", "Isaac", "Jade", "Kofi", "Lena", "Mateo", "Nora", "Omar", "Paula",
         "Quinn", "Rosa", "Sam", "Tara", "Uma", "Victor", "Wren", "Xavier", "Yusuf", "Zoe"]
LAST = ["Abara", "Bishop", "Castillo", "Dorsey", "Eklund", "Farrow", "Gill", "Hart", "Iqbal",
        "Jensen", "Kowalski", "Lindqvist", "Moreau", "Nakamura", "Oduya", "Pryce", "Quist",
        "Ramos", "Sato", "Thorne", "Ueda", "Vance", "Whitlock", "Xu", "Yilmaz", "Zane"]
COMPETITORS = ["Brightline Consulting", "Okafor & Wynn", "Northgate Advisory Group", "Teller Strategy"]
MONTHS = ["September", "October", "November", "December", "January", "February"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


@dataclass
class Item:
    id: str
    set: str
    text: str
    split: str
    labels: set[str] = field(default_factory=set)  # question keys this item is a true positive for
    kind: str = "background"  # background | positive | near_miss | negation


def _person(rng: random.Random, domain: str) -> tuple[str, str]:
    first, last = rng.choice(FIRST), rng.choice(LAST)
    return f"{first} {last}", f"{first.lower()}.{last.lower()}@{domain}"


def _thread(subject: str, client: str, messages: list[tuple[str, str]], when: str) -> str:
    parts = [f"Subject: {subject}", f"Client: {client}", ""]
    for i, (sender, body) in enumerate(messages):
        parts.append(f"[{when}, message {i + 1}] From: {sender}\n{body.strip()}\n")
    return "\n".join(parts).strip()


# ── background mail ──────────────────────────────────────────────────────

def _bg_mail(rng: random.Random) -> tuple[str, str, list[tuple[str, str]]]:
    client, domain = rng.choice(CLIENTS)
    name, addr = _person(rng, domain)
    first = name.split()[0]
    us = rng.choice(US)
    day, month, d = rng.choice(DAYS), rng.choice(MONTHS), rng.randint(2, 28)
    amt = rng.choice([1200, 2400, 3150, 4800, 6500, 7200, 9800, 12500])
    topic = rng.randrange(26)
    if topic == 0:
        return client, f"Workshop on {day}", [
            (addr, f"Hi Morgan, can we move the stakeholder workshop to {day} {month} {d}? Half the team is out the original week."),
            (us, f"{first}, {day} works. I'll resend the invite with the new room."),
        ]
    if topic == 1:
        return client, f"Invoice {rng.randint(1000, 9999)}", [
            (us, f"Hi {first}, attached is the invoice for {month} work, ${amt:,}. Net 30 as usual."),
            (addr, "Thanks, forwarded to accounts payable."),
        ]
    if topic == 2:
        return client, "Interview schedule for discovery", [
            (us, f"{first}, here are the six discovery interviews we'd like. Can your EA find 45 minutes with each?"),
            (addr, "Most are booked now. The CFO can only do the 14th."),
            (us, "The 14th is fine, thank you."),
        ]
    if topic == 3:
        return client, "Data request", [
            (us, f"Hi {first}, could you send last year's ticket export and the org chart? A CSV is fine."),
            (addr, rng.choice(["Uploaded both to the shared folder.", "IT says Thursday for the export.",
                               "Org chart attached; export to follow."])),
        ]
    if topic == 4:
        return client, "Parking and building access", [
            (addr, f"For {day}, park in lot C and check in at the front desk. Badges will be ready."),
        ]
    if topic == 5:
        return client, f"Notes from {day}'s steering meeting", [
            (us, f"{first}, notes attached. Decisions: pilot in two sites first, weekly check-ins, "
                 f"risk log owned by your PMO. Next meeting {month} {d}."),
        ]
    if topic == 6:
        return client, "Draft survey for frontline staff", [
            (us, f"Here is the draft 12-question survey. Any items you'd cut, {first}?"),
            (addr, "Question 7 is confusing; otherwise looks good."),
            (us, "Reworded 7. Sending the final tomorrow."),
        ]
    if topic == 7:
        return client, "Introduction", [
            (addr, f"Morgan, meet {rng.choice(FIRST)} from our finance team, who will own the reporting piece from here."),
            (us, "Thanks for the introduction. Happy to set up a call."),
        ]
    if topic == 8:
        return client, "Out of office", [
            (addr, f"I'm out until {month} {d} with limited email. For urgent items contact our office manager."),
        ]
    if topic == 9:
        return client, "Expense receipts", [
            (us, f"{first}, per the engagement letter, travel expenses for the site visit came to ${rng.randint(180, 900)}. Receipts attached."),
            (addr, "Approved."),
        ]
    if topic == 10:
        return client, "Holiday schedule", [
            (addr, f"Our offices close {month} {d} through the new year. Plan deliverables around that, please."),
            (us, "Noted, we'll land the draft report before then."),
        ]
    if topic == 11:
        return client, "Process map review", [
            (us, f"Attached is the current-state map for order intake. {rng.randint(14, 40)} steps, three handoffs we think can go."),
            (addr, "This is accurate. The credit check step is worse than drawn."),
        ]
    if topic == 12:
        return client, "Board deck slides", [
            (addr, "Can you send two slides summarising the findings for the board pack by Friday?"),
            (us, "Yes, you'll have them Thursday."),
        ]
    if topic == 13:
        return client, "Training session recording", [
            (us, f"The recording from {day}'s training is in the shared drive, with the slides."),
            (addr, "Great, I'll share it with the night shift."),
        ]
    if topic == 14:
        return client, "Conference next month", [
            (addr, f"Are either of you going to the regional operations conference in {month}? We could meet there."),
            (us, "Jordan will be there on day two."),
        ]
    if topic == 15:
        return client, "System access", [
            (us, f"{first}, our login to the reporting tool expired. Could IT reset it?"),
            (addr, "Reset. Check your email for the link."),
        ]
    if topic == 16:
        return client, "Pilot metrics week " + str(rng.randint(1, 12)), [
            (us, f"Pilot update: cycle time down {rng.randint(5, 30)}%, two exceptions this week, both resolved."),
            (addr, "Good progress. Can we add rework rate next week?"),
        ]
    if topic == 17:
        return client, "Change of contact", [
            (addr, f"I'm moving to a new role on {month} {d}. {rng.choice(FIRST)} {rng.choice(LAST)} will be your contact."),
            (us, f"Congratulations, {first}. We'll loop them in."),
        ]
    if topic == 18:
        return client, "Lunch order for Thursday", [
            (addr, "We'll order sandwiches for the working session. Any dietary needs on your side?"),
            (us, "One vegetarian, thanks."),
        ]
    if topic == 19:
        return client, "Policy document comments", [
            (us, "Comments on the draft escalation policy are in the margin. Section 4 contradicts the SLA."),
            (addr, "Legal agrees. We'll redraft section 4."),
        ]
    if topic == 20:
        return client, "Quick question about the dashboard", [
            (addr, "Why does the backlog chart drop on weekends? Is that a data issue?"),
            (us, "It's the weekend shift not logging. We'll footnote it."),
        ]
    if topic == 21:
        return client, "Signed SOW", [
            (addr, "Signed statement of work attached for the second phase."),
            (us, "Received, thank you. Kickoff as planned."),
        ]
    if topic == 22:
        return client, "Thank you", [
            (addr, f"Thanks for {day}. The team found the session really practical."),
        ]
    if topic == 23:
        return client, "Reschedule check-in", [
            (us, f"{first}, can we push our check-in by an hour on {day}?"),
            (addr, "Sure."),
        ]
    if topic == 24:
        return client, "Site visit agenda", [
            (us, f"Agenda for the {month} {d} site visit: 9:00 tour, 10:30 supervisors, 1:00 readout."),
            (addr, "Add 15 minutes with the safety lead after the tour, please."),
        ]
    return client, "Reference request", [
        (addr, "A peer at another organisation asked about your work with us. OK if I give them your email?"),
        (us, "Of course, thank you."),
    ]


# ── planted mail ──────────────────────────────────────────────────────────
# Q keys: renewal_price, competitor, at_risk. Each tuple: (labels, kind, client, subject, messages).
# `C:` sender means the client contact, `U:` us.

PLANTED_MAIL: list[tuple[set[str], str, str, str, list[tuple[str, str]]]] = [
    # renewal_price positives
    ({"renewal_price"}, "positive", "Harbor Freight Lines", "Re: next year", [
        ("C", "Before we sign up for another year, can we talk about the number? $48k felt steep for what we used in Q3."),
        ("U", "Fair. We can look at a lighter retainer at $40k with quarterly check-ins.")]),
    ({"renewal_price"}, "positive", "Cobalt Credit Union", "Extending the advisory retainer", [
        ("U", "Attached is the proposal to extend the retainer through 2027. The monthly fee moves from $3,500 to $3,800."),
        ("C", "The board will want to know why it's going up. Can you add a line on that?")]),
    ({"renewal_price"}, "positive", "Fenwick Tooling", "Phase 3", [
        ("C", "If we continue into phase 3, would you hold this year's day rate? Budget is frozen at last year's level."),
        ("U", "We can hold the rate if phase 3 starts before March.")]),
    ({"renewal_price"}, "positive", "Quarry Hill Bank", "Re: contract ending December", [
        ("C", "Our agreement ends in December. Procurement asked me for a quote to carry on as-is for 12 months."),
        ("U", "Same scope for 12 months would be $62,000, billed quarterly.")]),
    ({"renewal_price"}, "positive", "Tamarack Insurance", "Budget for 2027", [
        ("C", "I'm building the 2027 budget. What should I pencil in to keep you on for another year? Same coaching cadence."),
        ("U", "Pencil in $27k. That keeps the monthly cadence and adds one leadership offsite.")]),
    ({"renewal_price"}, "positive", "Wexford Hotels", "Re-up?", [
        ("C", "We'd like to re-up for another season. Is the fee the same?"),
        ("U", "It goes up 5% for inflation, to $15,750 for the season.")]),
    ({"renewal_price", "competitor"}, "positive", "Sable Logistics", "Renewal", [
        ("C", "Okafor & Wynn quoted us 20% less for a similar retainer. Can you get closer to their number if we renew?"),
        ("U", "We can't match it, but we can drop the second workshop and come down to $34k.")]),
    ({"renewal_price"}, "positive", "Pellucid Software", "Year two pricing", [
        ("U", "As we head into year two, here's the pricing we discussed: the platform-support block at $9k a quarter instead of $11k, since the setup work is done."),
        ("C", "That works. Send the paperwork.")]),
    ({"renewal_price"}, "positive", "Union Mill Textiles", "Keeping the arrangement going", [
        ("C", "Morgan, we'd like to keep the arrangement going after June. Can you send me what it would cost us? Finance wants it before the 15th."),
        ("U", "Will do by Friday. Same hours, same blended rate, so $5,200 a month.")]),
    ({"renewal_price"}, "positive", "Alder Grove Senior Living", "Discount for multi-year?", [
        ("C", "If we committed to two more years instead of one, is there a better rate?"),
        ("U", "Yes, 8% off the annual fee for a two-year renewal.")]),
    ({"renewal_price"}, "positive", "Redwater Utilities", "Purchase order for continuation", [
        ("C", "To raise the PO for the continuation I need the not-to-exceed figure."),
        ("U", "Not to exceed $88,500 for the continuation year, inclusive of travel.")]),
    ({"renewal_price"}, "positive", "Ironbridge Manufacturing", "Re: retainer", [
        ("C", "Honestly the retainer cost is the sticking point for another term. Can we move to pay-as-you-go?"),
        ("U", "We could do a block of 40 hours at $210/hour instead of the flat retainer.")]),
    # renewal_price near-misses and negations
    (set(), "near_miss", "Harbor Freight Lines", "Domain renewal notice", [
        ("C", "FYI our web domain renewal is due and the registrar raised the price. Nothing for you to do, just explaining the site outage last night.")]),
    (set(), "near_miss", "Cobalt Credit Union", "Pricing of the member product", [
        ("C", "For the workshop, can you prepare a slide on how we price our auto loans versus other credit unions?"),
        ("U", "Yes, we'll benchmark the rates.")]),
    (set(), "negation", "Fenwick Tooling", "Renewal", [
        ("C", "We've decided to renew for another year on the same terms. No changes to the fee, so no need to discuss price. Please send the renewal letter."),
        ("U", "Will do.")]),
    (set(), "near_miss", "Quarry Hill Bank", "Our software license", [
        ("U", "Internal note: our survey tool subscription renewal went from $900 to $1,100 a year. Do we still need it?"),
        ("U", "Keep it, we use it on every engagement.")]),
    (set(), "near_miss", "Tamarack Insurance", "Policy renewals backlog", [
        ("C", "The renewals team has 600 policies past their renewal date. Can the process work look at why renewals are so slow?"),
        ("U", "Yes, that's in scope for the mapping.")]),
    (set(), "near_miss", "Wexford Hotels", "Room rates for the offsite", [
        ("U", "For the leadership offsite, what room rate can you give our facilitators?"),
        ("C", "$129 a night, same as last time.")]),
    (set(), "negation", "Pellucid Software", "Not continuing", [
        ("C", "We won't be continuing after this phase. It's not about cost; the project is being folded into the parent company's program."),
        ("U", "Understood, thank you for telling us early.")]),
    (set(), "near_miss", "Union Mill Textiles", "Cotton price spike", [
        ("C", "Raw cotton prices are up 30%, so leadership wants the cost-reduction work to look at sourcing too."),
        ("U", "We'll add a sourcing workstream to the plan.")]),
    (set(), "near_miss", "Alder Grove Senior Living", "Invoice question", [
        ("C", "Invoice 4471 shows $6,500 but the SOW says $6,000 for October. Which is right?"),
        ("U", "$6,000; we'll reissue. Sorry for the error.")]),
    (set(), "near_miss", "Redwater Utilities", "Rate case", [
        ("C", "Our rate case with the commission was approved, so customer prices rise 4% next year. The comms plan needs to reflect that.")]),
    (set(), "near_miss", "Ironbridge Manufacturing", "Original proposal", [
        ("C", "Can you resend the original proposal from last spring? Our new COO wants to see the scope and fee we agreed for the current phase.")]),
    (set(), "near_miss", "Juniper County Schools", "Membership renewal for the association", [
        ("C", "Reminder that our state association membership renewal is $450 this year. Not related to your work, but the superintendent asked me to send the conference flyer along.")]),
    # competitor positives
    ({"competitor"}, "positive", "Maple Ridge Health", "Second opinion", [
        ("C", "Our CFO also asked Brightline Consulting to look at the revenue cycle. Can you two coordinate, or would you rather not?"),
        ("U", "We're happy to coordinate.")]),
    ({"competitor"}, "positive", "Dunmore Plastics", "RFP shortlist", [
        ("C", "You're on the shortlist with Northgate Advisory Group and one other firm. Final presentations are the 20th.")]),
    ({"competitor"}, "positive", "Elmstead Realty", "Where we landed", [
        ("C", "Thanks for the proposal. We've gone with Teller Strategy for this round; their team already knows our systems.")]),
    ({"competitor"}, "positive", "Foxglove Media", "Prior work", [
        ("C", "Some background: another advisory firm did a similar diagnostic for us in 2024 and the recommendations never landed. That's why the board is wary."),
        ("U", "Helpful context. Can we see that report?")]),
    ({"competitor"}, "positive", "Granite Peak Outfitters", "Compare approaches", [
        ("C", "Okafor & Wynn proposed doing this in six weeks. Why is your plan twelve?"),
        ("U", "Their plan skips the pilot. We can show you the difference.")]),
    ({"competitor"}, "positive", "Hollis & Reed Architects", "Working alongside", [
        ("C", "Heads up that the strategy firm our parent company hired will sit in on Thursday's readout.")]),
    ({"competitor"}, "positive", "Keel Marine Services", "Benchmark", [
        ("C", "The last consultants we used charged by deliverable, not by month. Could you price it that way?")]),
    ({"competitor"}, "positive", "Cascade Water Works", "Board feedback", [
        ("C", "Board members asked how you compare with Brightline. One of them used Brightline at her last utility.")]),
    ({"competitor"}, "positive", "Zephyr Aerospace Parts", "Two bids", [
        ("C", "We have two bids for the lean program, yours and one from a Big Four advisory practice. Can we talk Tuesday?")]),
    ({"competitor"}, "positive", "Verity Legal Aid", "Pro bono offer", [
        ("C", "A larger consulting firm has offered to do the strategic plan pro bono. I'd still rather work with you, but I have to show the board I considered it.")]),
    ({"competitor"}, "positive", "Yarrow Community Foundation", "Grantee capacity work", [
        ("C", "Several of our grantees have worked with Northgate on capacity building. We want your approach to be different from theirs.")]),
    # competitor near-misses and negations
    (set(), "near_miss", "Ostrander Foods", "Their competitors", [
        ("C", "For the market scan, include our three biggest competitors: Hillcrest Snacks, Pantry Co and Golden Mill.")]),
    (set(), "near_miss", "Birchwood Dental Group", "Competing priorities", [
        ("C", "We have competing priorities this quarter, so let's slow the cadence to every other week.")]),
    (set(), "negation", "Dunmore Plastics", "No other firms", [
        ("C", "To be clear, we are not talking to any other consultants. This is a direct engagement, no RFP.")]),
    (set(), "near_miss", "Elmstead Realty", "Competition among agents", [
        ("C", "Our agents compete with each other for listings, which is part of the culture problem you identified.")]),
    (set(), "near_miss", "Foxglove Media", "Our own consultant hire", [
        ("C", "We hired an internal process improvement lead, Wren Ueda, who will be your day-to-day partner.")]),
    (set(), "near_miss", "Granite Peak Outfitters", "Vendor selection", [
        ("C", "We're choosing between two e-commerce platforms. Can your team sit in on the demos?")]),
    (set(), "near_miss", "Hollis & Reed Architects", "Competition entry", [
        ("C", "We're entering the city library design competition, so the partners are busy until the 10th.")]),
    (set(), "negation", "Keel Marine Services", "Exclusive", [
        ("C", "The board decided against a competitive bid. We'll sole-source to you.")]),
    (set(), "near_miss", "Cascade Water Works", "Auditors", [
        ("C", "Our external auditors start fieldwork next week; they may ask for your process maps.")]),
    (set(), "near_miss", "Zephyr Aerospace Parts", "Brightline wiring harness", [
        ("C", "The delay is at our supplier, Brightline Harness Co. Their wiring parts are two weeks late.")]),
    (set(), "near_miss", "Verity Legal Aid", "Volunteer lawyers", [
        ("C", "Lawyers from two big firms volunteer at our clinic on Saturdays. Could the volunteer-scheduling work include them?")]),
    (set(), "near_miss", "Yarrow Community Foundation", "Peer foundation", [
        ("C", "A peer foundation, the Linden Trust, wants to hear about our work with you. Could you present at their retreat?")]),
    # at_risk positives
    ({"at_risk"}, "positive", "Juniper County Schools", "Frustrated", [
        ("C", "I'll be blunt: the last two deliverables were late and the board is asking whether we should keep going. We need to talk this week.")]),
    ({"at_risk"}, "positive", "Ostrander Foods", "Value", [
        ("C", "Leadership is questioning the value we're getting. Unless the pilot shows savings by March, I can't defend the spend.")]),
    ({"at_risk"}, "positive", "Birchwood Dental Group", "Pausing", [
        ("C", "We want to pause the engagement after this month while we decide whether to continue at all.")]),
    ({"at_risk"}, "positive", "Sable Logistics", "Not what we expected", [
        ("C", "Frankly the report read like a template. If phase two is the same, we'll take this in-house.")]),
    ({"at_risk"}, "positive", "Hollis & Reed Architects", "New managing partner", [
        ("C", "Our new managing partner is reviewing all outside advisors. She's not convinced we need you next year. Can you prepare a one-page case?")]),
    ({"at_risk"}, "positive", "Cobalt Credit Union", "Tone in the workshop", [
        ("C", "Several of my managers felt talked down to in Tuesday's session. If that happens again I'll have trouble keeping them engaged with this project, and with you.")]),
    # at_risk near-misses
    (set(), "near_miss", "Juniper County Schools", "Board meeting", [
        ("C", "The board meets Thursday to approve next year's budget. Your line item is on the consent agenda.")]),
    (set(), "negation", "Ostrander Foods", "Happy with progress", [
        ("C", "I know the pilot started slowly, but leadership is very happy with where it's landed. No concerns at all.")]),
    (set(), "near_miss", "Birchwood Dental Group", "Pausing the newsletter", [
        ("C", "We're pausing our patient newsletter for a month; unrelated to your work.")]),
    (set(), "near_miss", "Sable Logistics", "Late shipment", [
        ("C", "A customer is threatening to leave us over late shipments. That's exactly why the routing work matters.")]),
    (set(), "near_miss", "Hollis & Reed Architects", "Review of advisors", [
        ("C", "Our new managing partner reviewed outside advisors and kept you on. She wants a quarterly summary going forward.")]),
    (set(), "negation", "Cobalt Credit Union", "Workshop feedback", [
        ("C", "Managers said Tuesday's session was the most useful training they've had. One said she finally understood the risk framework.")]),
]


def mail_set(n_background: int = 1440) -> list[Item]:
    rng = random.Random(SEED)
    items: list[Item] = []
    for i in range(n_background):
        client, subject, msgs = _bg_mail(rng)
        when = f"{rng.choice(MONTHS)} {rng.randint(1, 28)}"
        items.append(Item(f"m{i:04d}", "mail", _thread(subject, client, msgs, when),
                          "dev" if rng.random() < 0.5 else "held"))
    for j, (labels, kind, client, subject, msgs) in enumerate(PLANTED_MAIL):
        domain = dict(CLIENTS)[client]
        name, addr = _person(rng, domain)
        resolved = [(addr if who == "C" else rng.choice(US), body) for who, body in msgs]
        when = f"{rng.choice(MONTHS)} {rng.randint(1, 28)}"
        items.append(Item(f"p{j:03d}", "mail", _thread(subject, client, resolved, when),
                          "dev" if j % 2 == 0 else "held", set(labels), kind))
    rng.shuffle(items)
    return items


MAIL_QUESTIONS = {
    "renewal_price": "Does this thread discuss the price or fee for continuing or renewing a client's engagement with us?",
    "competitor": "Does the client mention another consulting or advisory firm that they are considering, using, or comparing us with?",
    "at_risk": "Does the client signal that they are unhappy enough that they might end, pause or not renew their work with us?",
}
#: Rewordings for the robustness pass, written before the held-out pass.
MAIL_REWORDED = {
    "renewal_price": "Is the cost of extending or re-signing our engagement talked about in these emails?",
    "competitor": "Is a rival consultancy or another advisory firm referred to by the client in this correspondence?",
    "at_risk": "Is this client at risk of leaving us, judging by what they wrote?",
}
#: What a person would type into a plain substring search over the mailbox.
MAIL_KEYWORDS = {
    "renewal_price": ["renew", "renewal"],
    "competitor": ["competitor", "other firm", "another firm", "consultant"],
    "at_risk": ["unhappy", "cancel", "not renew", "pause"],
}


# ── promises and new emails ───────────────────────────────────────────────

PROMISE_TEMPLATES = [
    "Send the {thing} to {client} by {month} {d}.",
    "Deliver the {thing} for {client} before the {month} steering meeting.",
    "Review {client}'s {thing} and send comments by {month} {d}.",
    "Schedule the {thing} session with {client} in {month}.",
    "Share the draft {thing} with {first} at {client}.",
]
THINGS = ["process map", "current-state report", "survey results", "board summary slides", "pilot readout",
          "training plan", "interview synthesis", "risk register", "capacity model", "KPI dashboard",
          "change plan", "role descriptions", "SOP drafts", "budget scenarios", "vendor comparison"]

#: Three new client emails; each names the promises it affects (positives) and near-misses.
NEW_EMAILS = {
    "e1": ("Maple Ridge Health",
           "From: priya.oduya@mapleridge.example\nSubject: Changes to the plan\n\n"
           "Hi Morgan, a few updates. The board offsite moved to January 22, so the facilitation guide can wait "
           "until mid-January. We're cancelling the patient-flow data audit; the new EHR vendor will do it. "
           "I already sent you the interview list myself, so you don't need to chase our EA for it. "
           "Everything else stays as planned.\nPriya"),
    "e2": ("Fenwick Tooling",
           "From: marcus.hart@fenwick.example\nSubject: Re: next steps\n\n"
           "Morgan, our plant manager left last week, so please hold off on the supervisor training until we hire "
           "a replacement, probably March. The scrap-rate analysis is now more urgent: can we have it by the 5th "
           "instead of the 20th? And thanks for the 5S photos, received.\nMarcus"),
    "e3": ("Cobalt Credit Union",
           "From: elena.castillo@cobaltcu.example\nSubject: Board timing\n\n"
           "Hi both, the board moved the strategy session up two weeks, to November 4. We'll need the member "
           "survey results and the branch scenarios by October 28 now. The CEO letter you offered to draft is no "
           "longer needed; she wrote it herself.\nElena"),
}
PLANTED_PROMISES = [
    # (email, labels-positive?, kind, text)
    ("e1", True, "positive", "Send the board offsite facilitation guide to Maple Ridge Health by December 15."),
    ("e1", True, "positive", "Run the patient-flow data audit for Maple Ridge Health and report in November."),
    ("e1", True, "positive", "Get the stakeholder interview list from Maple Ridge Health's EA."),
    ("e1", True, "positive", "Book the facilitator and room for Maple Ridge Health's December board offsite."),
    ("e1", False, "near_miss", "Send Maple Ridge Health the discharge process map by November 10."),
    ("e1", False, "near_miss", "Draft the facilitation guide for Cascade Water Works' board retreat by December 15."),
    ("e1", False, "near_miss", "Share the interview synthesis with Maple Ridge Health's COO."),
    ("e1", False, "near_miss", "Run the data audit for Alder Grove Senior Living in November."),
    ("e2", True, "positive", "Deliver the supervisor training program for Fenwick Tooling in November."),
    ("e2", True, "positive", "Send Fenwick Tooling the scrap-rate analysis by the 20th."),
    ("e2", True, "positive", "Send Fenwick Tooling the 5S before-and-after photos."),
    ("e2", True, "positive", "Interview the Fenwick Tooling plant manager about shift handoffs."),
    ("e2", False, "near_miss", "Send Fenwick Tooling the maintenance backlog summary by the 20th."),
    ("e2", False, "near_miss", "Deliver the supervisor training program for Ironbridge Manufacturing in November."),
    ("e2", False, "near_miss", "Send Dunmore Plastics the scrap-rate analysis by the 20th."),
    ("e2", False, "near_miss", "Invoice Fenwick Tooling for October."),
    ("e3", True, "positive", "Send Cobalt Credit Union the member survey results by November 12."),
    ("e3", True, "positive", "Deliver the branch consolidation scenarios to Cobalt Credit Union before the November board session."),
    ("e3", True, "positive", "Draft the CEO letter to members for Cobalt Credit Union."),
    ("e3", True, "positive", "Prepare the facilitation agenda for Cobalt Credit Union's November 18 strategy session."),
    ("e3", False, "near_miss", "Send Cobalt Credit Union the lending process map."),
    ("e3", False, "near_miss", "Send Quarry Hill Bank the member survey results by November 12."),
    ("e3", False, "near_miss", "Draft the CEO letter to staff for Tamarack Insurance."),
    ("e3", False, "near_miss", "Share the call-center staffing model with Cobalt Credit Union in December."),
]


def promise_set(n_background: int = 576) -> list[Item]:
    rng = random.Random(SEED + 1)
    items: list[Item] = []
    # The three emailing clients' promises are all planted, so no templated promise
    # is silently affected by an email (label noise).
    others = [c for c, _ in CLIENTS if c not in {NEW_EMAILS[k][0] for k in NEW_EMAILS}]
    for i in range(n_background):
        client = rng.choice(others)
        text = rng.choice(PROMISE_TEMPLATES).format(
            thing=rng.choice(THINGS), client=client, month=rng.choice(MONTHS), d=rng.randint(1, 28),
            first=rng.choice(FIRST))
        items.append(Item(f"c{i:04d}", "promise", text, "dev" if rng.random() < 0.5 else "held"))
    for j, (email, positive, kind, text) in enumerate(PLANTED_PROMISES):
        items.append(Item(f"q{j:03d}", "promise", text, "dev" if j % 2 == 0 else "held",
                          {email} if positive else set(), kind))
    rng.shuffle(items)
    return items


PROMISE_QUESTION = ("Does this new email change, delay, bring forward, cancel or fulfil this promise "
                    "the firm made?")
PROMISE_REWORDED = "After this email, is this promise different from before (new date, no longer needed, already done)?"


# ── accounts ────────────────────────────────────────────────────────────

INDUSTRIES = [
    ("regional trucking company", "runs {n} trucks out of two terminals"),
    ("family-owned machine shop", "makes precision parts for agricultural equipment"),
    ("community bank", "has {n} branches and a growing small-business book"),
    ("primary care clinic group", "operates {n} family practice clinics; all lab work is sent to an outside reference lab"),
    ("senior living operator", "runs {n} assisted living communities"),
    ("county school district", "serves {n}00 students across rural campuses"),
    ("plastics injection molder", "supplies housings to appliance makers"),
    ("hotel management company", "manages {n} select-service hotels"),
    ("credit union", "serves {n},000 members"),
    ("software company", "sells scheduling software to field-service businesses"),
    ("food processor", "packs frozen vegetables for grocery private labels"),
    ("water utility", "serves {n},000 customers"),
    ("architecture firm", "designs schools and civic buildings"),
    ("nonprofit health center", "provides primary and behavioral health care to uninsured patients"),
    ("physical therapy chain", "runs {n} outpatient physical therapy locations"),
    ("insurance agency", "sells commercial lines to contractors"),
    ("hospital foundation", "raises money for a regional hospital"),
    ("staffing agency", "places travel nurses and allied health staff"),
    ("medical device distributor", "distributes orthopedic implants to surgery centers"),
    ("pharmacy chain", "operates {n} independent pharmacies"),
]
CITIES = ["Roanoke", "Lynchburg", "Blacksburg", "Salem", "Bedford", "Christiansburg", "Danville", "Martinsville"]

PLANTED_ACCOUNTS = [
    (True, "positive", "Blue Ridge Pathology Associates", "Independent pathology practice in Roanoke reading biopsies and running histology for six regional hospitals."),
    (True, "positive", "Valley Reference Labs", "CLIA-certified reference laboratory processing about 3,000 patient specimens a day for physician offices."),
    (True, "positive", "Clearwater Toxicology", "Provides drug and alcohol screening of urine and blood samples for employers and treatment programs, tested in its own accredited lab."),
    (True, "positive", "Summit Molecular Diagnostics", "Runs PCR and genetic tests on patient samples for oncology practices; 40 bench technologists."),
    (True, "positive", "Piedmont Regional Hospital Outreach", "Hospital outreach program whose core lab tests specimens from nursing homes and clinics across the region."),
    (True, "positive", "New River Women's Health", "OB-GYN group with an in-house laboratory that runs Pap and prenatal panels on site."),
    (True, "positive", "Bedford Blood & Plasma Testing", "Tests donated blood and plasma for infectious disease markers before release to hospitals."),
    (True, "positive", "Salem Allergy & Immunology", "Allergy practice that processes patient blood panels in its own moderate-complexity lab."),
    (True, "positive", "Lynchburg Sleep and Neurodiagnostics", "Sleep clinic that also operates a small clinical chemistry lab for its patients' metabolic panels."),
    (True, "positive", "Danville Dialysis Partners", "Dialysis provider whose central lab runs monthly bloodwork for 1,200 patients."),
    (True, "positive", "Martinsville Urgent Care", "Urgent care chain; each site has a CLIA-waived point-of-care lab, and a central lab handles cultures."),
    (True, "positive", "Christiansburg Veterans Clinic Lab Services", "Contractor that staffs and runs the specimen lab inside a veterans' outpatient clinic."),
    (False, "near_miss", "LabWorks Software", "Builds laboratory information system software sold to hospital labs; no lab of its own."),
    (False, "near_miss", "Ridgeline Scientific Supply", "Distributes centrifuges, pipettes and reagents to clinical laboratories in three states."),
    (False, "near_miss", "Blacksburg Materials Research Lab", "University spin-out testing polymer strength for aerospace customers."),
    (False, "negation", "Salem Family Medicine", "Family medicine practice; sends all blood draws to an outside reference lab and runs no testing on site."),
    (False, "near_miss", "Roanoke Photo Lab", "Film development and photo printing studio downtown."),
    (False, "near_miss", "Bedford Food Safety Testing", "Tests food products for pathogens and allergens for food manufacturers."),
    (False, "near_miss", "Valley Clinical Staffing", "Places lab technologists and phlebotomists with hospitals; it does not run a lab."),
    (False, "near_miss", "Piedmont Dental Studio", "Dental clinic with an in-house dental lab that makes crowns and bridges."),
    (False, "negation", "Lynchburg Health Partners", "Physician group that closed its in-house lab in 2025 and now uses a national lab for all testing."),
    (False, "near_miss", "Clinic Labs Marketing", "Marketing agency whose clients include clinics and laboratories."),
    (False, "near_miss", "Danville Environmental Analytics", "Tests drinking water and soil samples for municipalities."),
    (False, "near_miss", "Summit Clinical Research", "Runs drug trials for sponsors; specimens are shipped to the sponsor's central lab."),
]


def account_set(n_background: int = 776) -> list[Item]:
    rng = random.Random(SEED + 2)
    items: list[Item] = []
    for i in range(n_background):
        kind, desc = rng.choice(INDUSTRIES)
        name = f"{rng.choice(LAST)} {rng.choice(['Group', 'Partners', 'Co', 'Services', 'Holdings', 'Inc'])}"
        city = rng.choice(CITIES)
        text = (f"Account: {name}\nLocation: {city}\nSegment: {kind}\n"
                f"Description: A {kind} in {city} that {desc.format(n=rng.randint(3, 40))}. "
                f"About {rng.randint(20, 900)} employees.")
        items.append(Item(f"a{i:04d}", "account", text, "dev" if rng.random() < 0.5 else "held"))
    for j, (positive, kind, name, desc) in enumerate(PLANTED_ACCOUNTS):
        text = f"Account: {name}\nLocation: {rng.choice(CITIES)}\nDescription: {desc}"
        items.append(Item(f"r{j:03d}", "account", text, "dev" if j % 2 == 0 else "held",
                          {"clinical_lab"} if positive else set(), kind))
    rng.shuffle(items)
    return items


ACCOUNT_QUESTION = "Does this organisation run its own clinical or diagnostic laboratory that tests patient specimens?"
ACCOUNT_REWORDED = "Is patient sample testing done in a lab this organisation itself operates?"
ACCOUNT_KEYWORDS = ["lab"]
