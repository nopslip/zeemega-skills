"""Append-only JSONL event log for zeemap lifecycle events.

Each line is one JSON object. See zeemap-lifecycle-execution-plan.md for the
event schema. Stdlib-only; importable from any Hermes skill.

Concurrency: writes use O_APPEND with a single os.write() per event. POSIX
guarantees atomicity for writes <= PIPE_BUF (typically 4KB) on local
filesystems, so concurrent appenders won't interleave. Events must serialize
to <= 4KB (enforced at append time).
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Iterator

DEFAULT_LOG_PATH = Path.home() / ".hermes" / "skills" / "productivity" / "zeemap" / "log.jsonl"

REQUIRED_EVENT_FIELDS = ("uuid", "ts", "action")
KNOWN_ACTIONS = frozenset({
    "created",
    "edited",
    "schema_migrated",
    "tagged",
    "linked",
    "audit_run",
    "hidden",
    "unhidden",
})

PIPE_BUF_SAFETY = 4096


def _resolve_path(path: str | os.PathLike | None) -> Path:
    if path is not None:
        return Path(path)
    env_override = os.environ.get("ZEEMAP_LOG_PATH")
    if env_override:
        return Path(env_override)
    return DEFAULT_LOG_PATH


def append(event: dict, *, path: str | os.PathLike | None = None) -> None:
    """Append one event to the log. Atomic for lines under 4KB."""
    for field in REQUIRED_EVENT_FIELDS:
        if field not in event:
            raise ValueError(f"event missing required field: {field}")
    action = event["action"]
    if action not in KNOWN_ACTIONS:
        raise ValueError(f"unknown action: {action!r}")

    log_path = _resolve_path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n"
    encoded = line.encode("utf-8")
    if len(encoded) > PIPE_BUF_SAFETY:
        raise ValueError(
            f"event serializes to {len(encoded)} bytes; "
            f"limit is {PIPE_BUF_SAFETY} for atomic append"
        )

    fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, encoded)
    finally:
        os.close(fd)


def _iter_all(path: str | os.PathLike | None = None) -> Iterator[dict]:
    log_path = _resolve_path(path)
    if not log_path.exists():
        return
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def events_for(uuid: str, *, path: str | os.PathLike | None = None) -> list[dict]:
    """All events for a single zee, oldest first."""
    return [e for e in _iter_all(path) if e.get("uuid") == uuid]


def summary(uuid: str, *, path: str | os.PathLike | None = None) -> dict:
    """High-level stats for a single zee."""
    events = events_for(uuid, path=path)
    if not events:
        return {
            "edits": 0,
            "last_touched": None,
            "models_touched": [],
            "skills_touched": [],
            "actions": {},
        }
    models = Counter()
    skills = Counter()
    actions = Counter()
    edits = 0
    for e in events:
        actions[e["action"]] += 1
        if e["action"] in ("edited", "tagged", "linked", "schema_migrated"):
            edits += 1
        m = e.get("actor_model")
        if m:
            models[m] += 1
        s = e.get("skill")
        if s:
            skills[s] += 1
    return {
        "edits": edits,
        "last_touched": events[-1]["ts"],
        "models_touched": sorted(models),
        "skills_touched": sorted(skills),
        "actions": dict(actions),
    }


def recent(n: int = 50, *, path: str | os.PathLike | None = None) -> list[dict]:
    """Last n events across all zees, most recent first."""
    events = list(_iter_all(path))
    tail = events[-n:] if n > 0 else events
    tail.reverse()
    return tail
