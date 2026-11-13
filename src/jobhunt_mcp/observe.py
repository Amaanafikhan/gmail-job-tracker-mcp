"""Observability: log every tool call to a JSONL file and summarise the log.

Each line in the log is one tool call:
    {"ts": "...", "tool": "check_new_replies", "args": {"days": 7}, "ms": 41.2,
     "ok": true, "error": null, "result_chars": 96, "result": "You have 2 new replies..."}

The log lives at ~/.jobhunt-mcp/tool_calls.jsonl. Set JOBHUNT_LOG to move it,
or JOBHUNT_LOG=off to turn logging off. Logging never breaks a tool call:
if the file can't be written, the call still returns normally.

Run `jobhunt-stats` to see calls per tool, error rate and latency.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PREVIEW_CHARS = 200  # keep log lines short and avoid storing whole emails

# Tools answer with a sentence instead of raising, so a call can "succeed" while the
# user still didn't get what they asked for. These openings mark that soft failure.
SOFT_FAIL_PREFIXES = ("I couldn't", "I don't know", "Which company")


def is_soft_fail(text: str) -> bool:
    return text.startswith(SOFT_FAIL_PREFIXES)


def log_path() -> Path | None:
    value = os.environ.get("JOBHUNT_LOG", "")
    if value.lower() == "off":
        return None
    return Path(value) if value else Path.home() / ".jobhunt-mcp" / "tool_calls.jsonl"


def _write(record: dict[str, Any]) -> None:
    path = log_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass  # observability must never take the tool down


def observed(fn: Callable[..., str]) -> Callable[..., str]:
    """Wrap a tool so every call is timed and logged. Keeps the original signature,
    so the MCP server still builds the same tool schema from it."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        started = time.perf_counter()
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tool": fn.__name__,
            "args": kwargs if not args else {"_positional": list(args), **kwargs},
        }
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            record.update(ms=round((time.perf_counter() - started) * 1000, 1), ok=False,
                          error=f"{type(exc).__name__}: {exc}", soft_fail=False, result_chars=0, result=None)
            _write(record)
            raise
        text = str(result)
        record.update(ms=round((time.perf_counter() - started) * 1000, 1), ok=True, error=None,
                      soft_fail=is_soft_fail(text), result_chars=len(text), result=text[:PREVIEW_CHARS])
        _write(record)
        return result

    return wrapper


def read_log(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a half-written line shouldn't stop the report
    return rows


def _pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]


def summarise(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No tool calls logged yet."
    by_tool: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_tool.setdefault(r.get("tool", "?"), []).append(r)

    lines = [f"{len(rows)} tool calls, {rows[0].get('ts', '?')} to {rows[-1].get('ts', '?')}", ""]
    lines.append(f"{'tool':<22}{'calls':>7}{'errors':>8}{'soft fails':>12}{'p50 ms':>9}{'p95 ms':>9}")
    for tool, calls in sorted(by_tool.items(), key=lambda kv: -len(kv[1])):
        ms = [float(c.get("ms", 0)) for c in calls]
        errors = sum(1 for c in calls if not c.get("ok", True))
        soft = sum(1 for c in calls if c.get("soft_fail"))
        lines.append(f"{tool:<22}{len(calls):>7}{errors:>8}{soft:>12}{_pct(ms, 0.5):>9.1f}{_pct(ms, 0.95):>9.1f}")

    soft = [r for r in rows if r.get("soft_fail")]
    if soft:
        lines += ["", "Recent soft fails (tool answered, user didn't get what they asked):"]
        for r in soft[-5:]:
            lines.append(f"  {r.get('ts')}  {r.get('tool')}({json.dumps(r.get('args', {}))})  -> {r.get('result')}")

    failed = [r for r in rows if not r.get("ok", True)]
    if failed:
        lines += ["", "Recent errors:"]
        for r in failed[-5:]:
            lines.append(f"  {r.get('ts')}  {r.get('tool')}  {r.get('error')}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise the MCP tool-call log")
    parser.add_argument("--log", type=Path, default=None, help="log file (default: JOBHUNT_LOG or ~/.jobhunt-mcp/tool_calls.jsonl)")
    parser.add_argument("--tail", type=int, default=0, help="also print the last N calls")
    args = parser.parse_args()
    path = args.log or log_path() or Path.home() / ".jobhunt-mcp" / "tool_calls.jsonl"
    rows = read_log(path)
    print(summarise(rows))
    if args.tail and rows:
        print("\nLast calls:")
        for r in rows[-args.tail:]:
            status = "ERR" if not r.get("ok") else ("SOFT" if r.get("soft_fail") else "ok ")
            print(f"  {r.get('ts')}  {status} {r.get('tool')}({json.dumps(r.get('args', {}))})  "
                  f"{r.get('ms')} ms  -> {r.get('result') or r.get('error')}")


if __name__ == "__main__":
    main()
