"""OpenRouter chat calls with a response cache, shared by every arm.

Every response is cached in results/calls/<model>.jsonl under a hash of the exact request body and the
repeat index, so a replay makes no call. Failed calls are not cached. A spend cap covers every cached call
of every model together. Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALLS = HERE / "results" / "calls"
URL = "https://openrouter.ai/api/v1/chat/completions"
PRECISIONS = ["fp8", "fp16", "bf16", "fp32", "unknown"]
IGNORE = {"deepseek/deepseek-v4.1-flash": ["baseten", "decart"]}


class Offline(Exception):
    """A replay needed a response that is not in the cache."""


def slug(model: str) -> str:
    return model.split("/")[-1]


def spent_all() -> float:
    return sum(json.loads(line)["cost"] for p in CALLS.glob("*.jsonl") for line in p.read_text().splitlines())


class Cache:
    def __init__(self, model: str, key: str | None, max_cost: float):
        self.model, self.key, self.max_cost = model, key, max_cost
        self.path = CALLS / f"{slug(model)}.jsonl"
        self.rows: dict[str, dict] = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                r = json.loads(line)
                self.rows[r["key"]] = r
        self.spent = spent_all() if CALLS.exists() else 0.0
        self.lock = threading.Lock()
        self.pending: dict[str, threading.Event] = {}

    def get(self, body: dict, rep: int) -> dict:
        k = hashlib.sha256(json.dumps({"body": body, "rep": rep}, sort_keys=True).encode()).hexdigest()[:24]
        with self.lock:
            if k in self.rows:
                return self.rows[k]
            ev = self.pending.get(k)
            if ev is None:
                self.pending[k] = threading.Event()
        if ev is not None:
            ev.wait()
            return self.get(body, rep)
        try:
            if not self.key:
                raise Offline(k)
            if self.spent >= self.max_cost:
                raise Offline(f"spend cap reached (${self.spent:.4f})")
            row = fetch(body, self.key)
            if not row.get("ok"):
                raise Offline(f"call failed: {row.get('error')}")
            row["key"], row["model"] = k, self.model
            with self.lock:
                self.rows[k] = row
                self.spent += row["cost"]
                CALLS.mkdir(parents=True, exist_ok=True)
                with self.path.open("a") as f:
                    f.write(json.dumps(row, sort_keys=True) + "\n")
            return row
        finally:
            with self.lock:
                self.pending.pop(k).set()


def fetch(body: dict, key: str) -> dict:
    data = json.dumps(body).encode()
    err = ""
    for attempt in range(4):
        req = urllib.request.Request(URL, data=data, method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read())
        except urllib.error.HTTPError as exc:
            err = f"HTTP {exc.code} {exc.read()[:200]!r}"
            time.sleep(2 + 3 * attempt)
            continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            err = repr(exc)
            time.sleep(2 + 3 * attempt)
            continue
        if not d.get("choices"):
            err = f"no choices: {str(d)[:200]}"
            time.sleep(2 + 3 * attempt)
            continue
        c = d["choices"][0]
        m = c.get("message") or {}
        u = d.get("usage") or {}
        return {"ok": True, "finish": c.get("finish_reason"), "content": m.get("content") or "",
                "tool_calls": [{"id": t.get("id", ""), "name": t["function"]["name"],
                                "arguments": t["function"].get("arguments") or ""}
                               for t in (m.get("tool_calls") or [])],
                "prompt_tokens": u.get("prompt_tokens") or 0, "completion_tokens": u.get("completion_tokens") or 0,
                "cost": float(u.get("cost") or 0), "provider": d.get("provider"),
                "ms": round((time.perf_counter() - t0) * 1000)}
        print(f"  retry: {err}", file=sys.stderr)
    return {"ok": False, "error": err}


class Ctx:
    """One run's view of the model: counts its calls and cost."""

    def __init__(self, cache: Cache, rep: int):
        self.cache, self.rep = cache, rep
        self.calls = self.prompt_tokens = 0
        self.cost = 0.0

    def chat(self, messages: list, tools: list | None = None, room: int = 4096) -> dict:
        provider = {"zdr": True, "sort": "throughput", "quantizations": PRECISIONS, "require_parameters": True}
        if self.cache.model in IGNORE:
            provider["ignore"] = IGNORE[self.cache.model]
        body = {"model": self.cache.model, "messages": messages, "max_tokens": room, "temperature": 0.3,
                "provider": provider, "usage": {"include": True}}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        r = self.cache.get(body, self.rep)
        self.calls += 1
        self.prompt_tokens += r["prompt_tokens"]
        self.cost += r["cost"]
        return r
