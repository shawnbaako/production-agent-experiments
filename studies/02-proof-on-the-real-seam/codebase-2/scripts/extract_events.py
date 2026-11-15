"""Normalize Claude Code, Codex and Pi transcripts into one event stream.

Each output row: harness, session, ts, kind (cmd|edit|read|mcp|other), name, target
(command or path), diff_add/diff_del (edited lines), out_chars, is_error, tokens_in/out
for the step when known. Only sessions whose working directory matches PROJECT_FILTER are kept.

Usage: python3 extract_events.py > data/events.jsonl
Raw transcripts never leave this machine; only this derived, secret-free stream is analyzed.
"""

import glob
import json
import os
import re
import sys

HOME = os.path.expanduser("~")
PROJECT_FILTER = os.environ["PROJECT_FILTER"]  # regex matching your checkout path(s)
PROJECT = re.compile(PROJECT_FILTER, re.I)
seen_ids: set[str] = set()


def emit(**row):
    sys.stdout.write(json.dumps(row) + "\n")


def text_len(content) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(c.get("text", "")) if isinstance(c, dict) else len(str(c)) for c in content)
    return len(json.dumps(content)) if content else 0


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def result_summary(txt: str) -> dict:
    """Pull pytest/vitest/playwright pass-fail counts out of a tool result."""
    out = {}
    tail = txt[-4000:]
    for key, pat in (
        ("passed", r"(\d+) passed"),
        ("failed", r"(\d+) failed"),
        ("errors", r"(\d+) errors?\b"),
        ("skipped", r"(\d+) skipped"),
    ):
        m = re.findall(pat, tail)
        if m:
            out[key] = int(m[-1])
    return out


# ---------------- Claude Code ----------------
def claude():
    for f in glob.glob(f"{HOME}/.claude/projects/**/*.jsonl", recursive=True):
        if not PROJECT.search(f):
            continue
        session = os.path.basename(f).removesuffix(".jsonl")
        sidechain = "/subagents/" in f
        pending = {}
        try:
            fh = open(f)
        except OSError:
            continue
        for line in fh:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = o.get("message")
            if not isinstance(msg, dict):
                continue
            ts = o.get("timestamp")
            content = msg.get("content")
            if o.get("type") == "assistant":
                usage = msg.get("usage") or {}
                mid = msg.get("id")
                if mid and ("u" + mid) not in seen_ids and usage:
                    seen_ids.add("u" + mid)
                    emit(
                        harness="claude",
                        session=session,
                        sidechain=sidechain,
                        ts=ts,
                        kind="usage",
                        model=msg.get("model"),
                        tokens_in=usage.get("input_tokens", 0)
                        + usage.get("cache_read_input_tokens", 0)
                        + usage.get("cache_creation_input_tokens", 0),
                        tokens_out=usage.get("output_tokens", 0),
                    )
                for c in content if isinstance(content, list) else []:
                    if c.get("type") != "tool_use" or c["id"] in seen_ids:
                        continue
                    seen_ids.add(c["id"])
                    pending[c["id"]] = (ts, c["name"], c.get("input") or {})
            elif o.get("type") == "user":
                if isinstance(content, str) and not o.get("isMeta"):
                    emit(
                        harness="claude",
                        session=session,
                        sidechain=sidechain,
                        ts=ts,
                        kind="user",
                        chars=len(content),
                    )
                for c in content if isinstance(content, list) else []:
                    if c.get("type") != "tool_result" or c.get("tool_use_id") not in pending:
                        continue
                    t0, name, inp = pending.pop(c["tool_use_id"])
                    txt = text_of(c.get("content"))
                    row = dict(
                        harness="claude",
                        session=session,
                        sidechain=sidechain,
                        ts=t0,
                        name=name,
                        out_chars=len(txt),
                        is_error=bool(c.get("is_error")),
                    )
                    if name == "Bash":
                        row.update(
                            kind="cmd", target=inp.get("command", "")[:2000], **result_summary(txt)
                        )
                    elif name in ("Edit", "MultiEdit"):
                        edits = inp.get("edits") or [inp]
                        row.update(
                            kind="edit",
                            target=inp.get("file_path", ""),
                            plus="\n".join(e.get("new_string", "") for e in edits)[:6000],
                            minus="\n".join(e.get("old_string", "") for e in edits)[:6000],
                        )
                    elif name == "Write":
                        row.update(
                            kind="edit",
                            target=inp.get("file_path", ""),
                            plus=inp.get("content", "")[:6000],
                            minus="",
                            write=True,
                        )
                    elif name in ("Read", "Grep", "Glob"):
                        row.update(
                            kind="read",
                            target=str(
                                inp.get("file_path") or inp.get("path") or inp.get("pattern") or ""
                            ),
                        )
                    elif name.startswith("mcp__"):
                        row.update(kind="mcp", target=json.dumps(inp)[:500])
                    elif name in ("Agent", "Task"):
                        row.update(kind="agent", target=(inp.get("description") or "")[:200])
                    else:
                        row.update(kind="other", target="")
                    emit(**row)


# ---------------- Codex ----------------
def codex():
    for f in glob.glob(f"{HOME}/.codex/sessions/**/*.jsonl", recursive=True):
        session = os.path.basename(f).removesuffix(".jsonl")
        in_project = None
        pending_cmd = {}
        try:
            fh = open(f)
        except OSError:
            continue
        for line in fh:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = o.get("payload")
            if not isinstance(p, dict):
                continue
            ts = o.get("timestamp")
            if o["type"] == "session_meta":
                in_project = bool(PROJECT.search(str(p.get("cwd", ""))))
                sub = bool(p.get("parent_thread_id"))
                continue
            if in_project is False:
                break
            if o["type"] == "event_msg" and p.get("type") == "token_count":
                last = (p.get("info") or {}).get("last_token_usage") or {}
                if last:
                    emit(
                        harness="codex",
                        session=session,
                        sidechain=sub,
                        ts=ts,
                        kind="usage",
                        tokens_in=last.get("input_tokens", 0),
                        tokens_out=last.get("output_tokens", 0),
                    )
            if o["type"] == "event_msg" and p.get("type") == "item_completed":
                it = p.get("item") or {}
                t = it.get("type")
                if it.get("id") in seen_ids:
                    continue
                seen_ids.add(it.get("id"))
                if t == "CommandExecution":
                    cmd = it.get("command")
                    cmd = cmd[-1] if isinstance(cmd, list) else str(cmd)
                    out = str(it.get("aggregated_output") or it.get("output") or "")
                    emit(
                        harness="codex",
                        session=session,
                        sidechain=sub,
                        ts=ts,
                        kind="cmd",
                        name="exec",
                        target=cmd[:2000],
                        out_chars=len(out),
                        is_error=it.get("exit_code") not in (0, None),
                        **result_summary(out),
                    )
                elif t == "FileChange":
                    for path, ch in (it.get("changes") or {}).items():
                        diff = ch.get("unified_diff") or ch.get("content") or ""
                        plus = "\n".join(
                            l[1:]
                            for l in diff.splitlines()
                            if l.startswith("+") and not l.startswith("+++")
                        )
                        minus = "\n".join(
                            l[1:]
                            for l in diff.splitlines()
                            if l.startswith("-") and not l.startswith("---")
                        )
                        emit(
                            harness="codex",
                            session=session,
                            sidechain=sub,
                            ts=ts,
                            kind="edit",
                            name="apply_patch",
                            target=path,
                            plus=plus[:6000],
                            minus=minus[:6000],
                            write=ch.get("type") == "add",
                        )
                elif t == "McpToolCall":
                    emit(
                        harness="codex",
                        session=session,
                        sidechain=sub,
                        ts=ts,
                        kind="mcp",
                        name=f"mcp__{it.get('server')}__{it.get('tool')}",
                        target=json.dumps(it.get("arguments"))[:500],
                        is_error=it.get("status") == "failed",
                    )
                elif t == "UserMessage":
                    emit(
                        harness="codex",
                        session=session,
                        sidechain=sub,
                        ts=ts,
                        kind="user",
                        chars=text_len(it.get("content")),
                    )


# ---------------- Pi ----------------
def pi():
    for f in glob.glob(f"{HOME}/.pi/agent*/sessions/**/*.jsonl", recursive=True):
        session = os.path.basename(f).removesuffix(".jsonl")
        pending = {}
        in_project = bool(PROJECT.search(f))
        try:
            fh = open(f)
        except OSError:
            continue
        for line in fh:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("type") == "session":
                in_project = in_project or bool(PROJECT.search(str(o.get("cwd", ""))))
            if not in_project or o.get("type") != "message":
                continue
            m = o["message"]
            ts = o.get("timestamp")
            if m.get("role") == "assistant":
                u = m.get("usage") or {}
                if u:
                    emit(
                        harness="pi",
                        session=session,
                        sidechain=False,
                        ts=ts,
                        kind="usage",
                        model=m.get("model"),
                        tokens_in=(u.get("input") or 0) + (u.get("cacheRead") or 0),
                        tokens_out=u.get("output") or 0,
                    )
                for c in m.get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "toolCall":
                        pending[c["id"]] = (ts, c["name"], c.get("arguments") or {})
            elif m.get("role") == "user":
                emit(
                    harness="pi",
                    session=session,
                    sidechain=False,
                    ts=ts,
                    kind="user",
                    chars=text_len(m.get("content")),
                )
            elif m.get("role") == "toolResult" and m.get("toolCallId") in pending:
                t0, name, a = pending.pop(m["toolCallId"])
                txt = text_of(m.get("content"))
                row = dict(
                    harness="pi",
                    session=session,
                    sidechain=False,
                    ts=t0,
                    name=name,
                    out_chars=len(txt),
                    is_error=bool(m.get("isError")),
                )
                if name == "bash":
                    row.update(
                        kind="cmd", target=a.get("command", "")[:2000], **result_summary(txt)
                    )
                elif name == "edit":
                    edits = a.get("edits") or [a]
                    row.update(
                        kind="edit",
                        target=a.get("path", ""),
                        plus="\n".join(e.get("newText", "") for e in edits)[:6000],
                        minus="\n".join(e.get("oldText", "") for e in edits)[:6000],
                    )
                elif name == "write":
                    row.update(
                        kind="edit",
                        target=a.get("path", ""),
                        plus=a.get("content", "")[:6000],
                        minus="",
                        write=True,
                    )
                elif name in ("read", "grep", "find", "ls"):
                    row.update(kind="read", target=str(a.get("path") or a.get("pattern") or ""))
                elif name.startswith("browser_"):
                    row.update(kind="mcp", target=json.dumps(a)[:300])
                else:
                    row.update(kind="other", target="")
                emit(**row)


if __name__ == "__main__":
    claude()
    codex()
    pi()
