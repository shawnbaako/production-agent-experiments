"""Shared plumbing: the extractor's output contract and prompt, OpenRouter calls, the spend cap.

The output models, the prompt, the request bodies and the input sanitiser are copied from the
production study. Calls go through OpenRouter with the cost OpenRouter reports, and every cost
is appended to results/spend.jsonl. A call is refused once recorded spend reaches the cap.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RESULTS = HERE / "results"
SOURCES = DATA / "sources.json"
SPEND = RESULTS / "spend.jsonl"
UA = "production-agent-experiments/1.0 (research script)"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
EXTRACT_MODEL = "deepseek/deepseek-v4.1-flash-1017"
MAX_INPUT_CHARS = 60_000
MAX_OUTPUT_TOKENS = 16_000
BUDGET_USD = 5.0


# --- Output contract (production operator-source-v3) ----------------------------------------


class _Fact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Literal["observed", "inferred", "contradictory", "unknown"] = "unknown"
    excerpt: str | None = None


class TextFact(_Fact):
    value: str | None = None


class IntFact(_Fact):
    value: int | None = Field(default=None, ge=0)


class ListFact(_Fact):
    value: list[str] | None = None


class KindFact(_Fact):
    value: Literal["experience", "stay", "rental", "other"] | None = None


class BasisFact(_Fact):
    value: Literal["per_person", "per_seat", "per_unit", "per_commitment"] | None = None


class ProposedOffering(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: TextFact
    kind: KindFact = Field(default_factory=KindFact)
    description: TextFact = Field(default_factory=TextFact)
    location: TextFact = Field(default_factory=TextFact)
    price_minor: IntFact = Field(default_factory=IntFact)
    includes: ListFact = Field(default_factory=ListFact)
    requirements: ListFact = Field(default_factory=ListFact)
    languages: ListFact = Field(default_factory=ListFact)
    duration_minutes: IntFact = Field(default_factory=IntFact)
    capacity: IntFact = Field(default_factory=IntFact)
    minimum_age: IntFact = Field(default_factory=IntFact)
    price_basis: BasisFact = Field(default_factory=BasisFact)
    price_wording: TextFact = Field(default_factory=TextFact)
    cancellation_wording: TextFact = Field(default_factory=TextFact)
    schedule_wording: TextFact = Field(default_factory=TextFact)
    matches_offering_id: str | None = None
    photo_numbers: list[int] = Field(default_factory=list)


class BusinessSuggestion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: TextFact = Field(default_factory=TextFact)
    city: TextFact = Field(default_factory=TextFact)
    state: TextFact = Field(default_factory=TextFact)
    phone: TextFact = Field(default_factory=TextFact)
    email: TextFact = Field(default_factory=TextFact)
    website: TextFact = Field(default_factory=TextFact)


class SourceExtraction(BaseModel):
    offerings: list[ProposedOffering] = Field(default_factory=list, max_length=20)
    business: BusinessSuggestion | None = None
    notes: str | None = None


OFFER_FIELDS = [
    name
    for name in ProposedOffering.model_fields
    if name not in {"matches_offering_id", "photo_numbers"}
]
BUSINESS_FIELDS = list(BusinessSuggestion.model_fields)


def system_prompt() -> str:
    """The production extraction prompt, rendered: two template comments leave two newlines."""
    schema = json.dumps(SourceExtraction.model_json_schema(), separators=(",", ":"))
    return "\n\n" + (HERE / "extract_prompt.txt").read_text().replace("{{ schema }}", schema)


# --- Untrusted text (production sanitiser) ---------------------------------------------------

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B-\x1F]")
_ROLE_MARKERS = {
    "assistant:": "assistant\\:",
    "system:": "system\\:",
    "user:": "user\\:",
    "<|im_start|>": "<\\|im_start\\|>",
    "<|im_end|>": "<\\|im_end\\|>",
    "<|endoftext|>": "<\\|endoftext\\|>",
}


def sanitize(content: str, *, max_chars: int = 4_000) -> str:
    """Neutralize prompt-boundary escapes inside text written by someone else."""
    sanitized = _CONTROL_CHARS_RE.sub("", content)
    for marker, replacement in _ROLE_MARKERS.items():
        sanitized = re.sub(re.escape(marker), replacement, sanitized, flags=re.IGNORECASE)
    sanitized = sanitized.replace("```", "`\\`\\`")
    sanitized = re.sub(r"</\s*untrusted\s*>", r"<\\/UNTRUSTED>", sanitized, flags=re.IGNORECASE)
    return sanitized[: max(1, max_chars)]


def sources() -> list[dict[str, Any]]:
    return json.loads(SOURCES.read_text())


def user_prompt(source: dict[str, Any]) -> str:
    """Production's user message for a pasted-text source with no existing offerings.

    The section is given as a text file, not as a Wikivoyage web page: given the page URL the
    extractor declined some sections as a guide's round-up rather than an operator's material.
    """
    head = (
        "Existing offerings (id | title):\nnone\n\n"
        f"Source kind: text; observed {source['revision_timestamp']}; file {source['id']}.txt"
        "\n\n"
    )
    budget = max(1_000, MAX_INPUT_CHARS - len(head) - 40)
    return f"{head}<UNTRUSTED>\n{sanitize(source['text'], max_chars=budget)}\n</UNTRUSTED>"


# --- Spend ledger ----------------------------------------------------------------------------

_LOCK = threading.Lock()


def spent() -> float:
    if not SPEND.exists():
        return 0.0
    return sum(json.loads(line)["usd"] for line in SPEND.read_text().splitlines() if line)


def record_spend(stage: str, usd: float) -> None:
    with _LOCK:
        RESULTS.mkdir(exist_ok=True)
        with SPEND.open("a") as ledger:
            ledger.write(json.dumps({"stage": stage, "usd": round(usd, 8)}) + "\n")


def check_budget() -> None:
    if spent() >= BUDGET_USD * 0.95:
        raise SystemExit(f"spend cap: ${spent():.4f} of ${BUDGET_USD} recorded; no more calls")


def post(url: str, body: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any]]:
    """POST JSON to OpenRouter; (status, payload). The key comes from the environment."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.load(error)
        except ValueError:
            return error.code, {"error": {"code": error.code, "message": str(error)}}


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    provider: str | None
    cost_usd: float
    input_tokens: int
    output_tokens: int
    seconds: float
    error: str | None = None


def chat(
    stage: str,
    model: str,
    system: str,
    user: str,
    *,
    json_mode: bool = False,
    reasoning_effort: str | None = "low",
    max_tokens: int = MAX_OUTPUT_TOKENS,
    timeout: float = 180.0,
) -> Completion:
    """One OpenRouter chat completion (production request body) with its reported cost."""
    check_budget()
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "usage": {"include": True},
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if reasoning_effort:
        body["reasoning"] = {"effort": reasoning_effort}
    for attempt in range(5):
        started = time.monotonic()
        try:
            status, payload = post(OPENROUTER_URL, body, timeout)
        except (OSError, ValueError) as error:
            return Completion("", model, None, 0.0, 0, 0, time.monotonic() - started, repr(error))
        # Upstream 429s: back off; latency counts the last try.
        if status != 429 and (payload.get("error") or {}).get("code") != 429:
            break
        time.sleep(5 * 2**attempt)
    seconds = time.monotonic() - started
    usage = payload.get("usage") or {}
    cost = float(usage.get("cost") or 0.0)
    record_spend(stage, cost)
    if "error" in payload or not payload.get("choices"):
        message = str(payload.get("error", payload))[:300]
        return Completion("", model, None, cost, 0, 0, seconds, message)
    return Completion(
        text=payload["choices"][0]["message"].get("content") or "",
        model=payload.get("model", model),
        provider=payload.get("provider"),
        cost_usd=cost,
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        seconds=seconds,
    )


# --- The quote check every arm runs on top of (production baseline) ---------------------------


def normalized(text: str) -> str:
    return " ".join((text or "").lower().split())


def baseline_status(status: str, excerpt: str | None, read_text: str) -> str:
    """Production's quote check for a text source: an observed excerpt must be in the text."""
    if status != "observed":
        return status
    haystack, needle = normalized(read_text), normalized(excerpt or "")
    if haystack and needle and needle in haystack:
        return "observed"
    return "inferred" if haystack else "observed"


def numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:[.,]\d+)?", text or "")
