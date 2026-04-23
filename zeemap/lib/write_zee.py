#!/home/dev/.hermes/hermes-agent/venv/bin/python
"""Emit a well-formed zee and append a 'created' event to the log.

Any Hermes skill can shell out to this to produce a schema_version:1 zee
in one call. Routes through ZeeStore — so when ZEEMAP_STORE=postgres the
write lands in the `zees` + `zee_events` tables and fires pg_notify for
the viewer; when ZEEMAP_STORE=local (default), writes the .md + appends
log.jsonl exactly as before.

Exit codes:
  0 — written
  2 — missing required CLI arg or bad input
  3 — slug collision (caller should retry with disambiguator)
  4 — log/event append failed (zee itself persisted; audit will see it)
  5 — postgres mode requires CLERK_USER_ID env and it isn't set

See zeemap-lifecycle-execution-plan.md §"Cron-output helper" for the contract.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import uuid as uuid_mod
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import log  # noqa: E402
# lib.store is imported lazily inside main() to avoid a circular import —
# store.py imports build_frontmatter / build_filename from this module.

DEFAULT_DATA_DIR = Path.home() / ".hermes" / "skills" / "productivity" / "zeemap" / "data"
SCHEMA_VERSION = 1
SLUG_WORD_LIMIT = 5


def _slugify(title: str) -> str:
    """Lowercase, hyphen-separated, 2-5 words max. Matches isZeeFilename."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not cleaned:
        raise ValueError("title produces empty slug")
    words = [w for w in cleaned.split("-") if w]
    return "-".join(words[:SLUG_WORD_LIMIT])


def _yaml_dq(value: str) -> str:
    """Double-quoted YAML scalar. Escape backslashes and double-quotes."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def _split_csv(s: str | None) -> list[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def build_frontmatter(fields: dict) -> str:
    """Render the required + optional frontmatter block (no delimiters)."""
    lines: list[str] = []
    # Required
    lines.append(f"created: {fields['created']}")
    lines.append(f"type: {fields['type']}")
    lines.append(f"zone: {fields['zone']}")
    lines.append(f"title: {_yaml_dq(fields['title'])}")
    lines.append(f"tags: {_yaml_list(fields['tags'])}")
    lines.append(f"what: {_yaml_dq(fields['what'])}")
    lines.append(f"why: {_yaml_dq(fields['why'])}")
    lines.append(f"uuid: {fields['uuid']}")
    lines.append(f"schema_version: {fields['schema_version']}")
    # Optional
    if fields.get("model"):
        lines.append(f"model: {fields['model']}")
    if fields.get("skill"):
        lines.append(f"skill: {fields['skill']}")
    if fields.get("skill_url"):
        lines.append(f"skill_url: {fields['skill_url']}")
    if fields.get("seeded_from"):
        lines.append(f"seeded_from: {_yaml_list(fields['seeded_from'])}")
    return "\n".join(lines)


def build_filename(created_iso: str, title: str) -> str:
    ts = dt.datetime.fromisoformat(created_iso).strftime("%Y-%m-%d-%H%M")
    return f"{ts}-{_slugify(title)}.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Emit a schema_version:1 zee.")
    p.add_argument("--title", required=True)
    p.add_argument("--body-file", required=True,
                   help="Path to file containing the zee body (markdown).")
    p.add_argument("--zone", required=True)
    p.add_argument("--tags", required=True,
                   help="Comma-separated tags, e.g. 'models,research'")
    p.add_argument("--what", required=True)
    p.add_argument("--why", required=True)
    p.add_argument("--type", required=True, dest="type_")
    p.add_argument("--skill", default=None)
    p.add_argument("--skill-url", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--session-id", default=None)
    p.add_argument("--seeded-from", default=None,
                   help="Comma-separated UUIDs")
    p.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    p.add_argument("--log-path", default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="Print frontmatter + log event; write nothing.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    body_path = Path(args.body_file)
    if not body_path.is_file():
        print(f"error: --body-file not found: {body_path}", file=sys.stderr)
        return 2

    created = dt.datetime.now().replace(microsecond=0).isoformat(timespec="seconds")
    zee_uuid = str(uuid_mod.uuid4())
    tags = _split_csv(args.tags)
    if not tags:
        print("error: --tags must include at least one tag", file=sys.stderr)
        return 2
    seeded_from = _split_csv(args.seeded_from)

    fields = {
        "created": created,
        "type": args.type_,
        "zone": args.zone,
        "title": args.title,
        "tags": tags,
        "what": args.what,
        "why": args.why,
        "uuid": zee_uuid,
        "schema_version": SCHEMA_VERSION,
        "model": args.model,
        "skill": args.skill,
        "skill_url": args.skill_url,
        "seeded_from": seeded_from,
    }

    try:
        filename = build_filename(created, args.title)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    data_dir = Path(args.data_dir).expanduser()
    target = data_dir / filename
    frontmatter = build_frontmatter(fields)
    body = body_path.read_text(encoding="utf-8")
    document = f"---\n{frontmatter}\n---\n\n{body}"
    if not document.endswith("\n"):
        document += "\n"

    event = {
        "uuid": zee_uuid,
        "ts": created,
        "action": "created",
        "actor_model": args.model,
        "session_id": args.session_id,
        "skill": args.skill,
        "note": None,
    }

    if args.dry_run:
        print("--- filename ---")
        print(filename)
        print("--- frontmatter ---")
        print(frontmatter)
        print("--- log event ---")
        import json
        print(json.dumps(event, indent=2, sort_keys=True))
        return 0

    # Route through the store adapter — local mode writes the .md, postgres
    # mode INSERTs into zees + zee_events and fires pg_notify.
    # Lazy import: store.py imports helpers from this module.
    from lib.store import (
        LocalMarkdownStore,
        LogEvent,
        PostgresStore,
        SlugCollisionError,
        Zee,
    )

    backend = os.environ.get("ZEEMAP_STORE", "local").strip().lower()
    clerk_user = os.environ.get("CLERK_USER_ID", "").strip()
    if backend == "postgres" and not clerk_user:
        print("error: ZEEMAP_STORE=postgres requires CLERK_USER_ID env",
              file=sys.stderr)
        return 5

    # Construct the store directly (not via get_store()) so --data-dir /
    # --log-path CLI args are honored in local mode.
    if backend == "postgres":
        store = PostgresStore()
    elif backend == "local":
        store = LocalMarkdownStore(
            data_dir=args.data_dir,
            log_path=args.log_path,
        )
    else:
        print(f"error: unknown ZEEMAP_STORE={backend!r}", file=sys.stderr)
        return 2
    # Local mode: user_id is a no-op (see LocalMarkdownStore). Postgres
    # mode: resolve Clerk subject → internal users.id UUID.
    user_id = store.resolve_user(clerk_user) if clerk_user else ""

    zee = Zee(
        uuid=zee_uuid,
        user_id=user_id,
        title=args.title,
        body=body,
        created=created,
        zone=args.zone,
        tags=tags,
        what=args.what,
        why=args.why,
        schema_version=SCHEMA_VERSION,
        type=args.type_,
        model=args.model,
        skill=args.skill,
        skill_url=args.skill_url,
        updated=None,
        seeded_from=seeded_from,
    )

    try:
        store.put(zee)
    except SlugCollisionError as e:
        print(f"error: slug collision at {target} ({e})", file=sys.stderr)
        return 3

    # Store handles the event append for both backends: LocalMarkdownStore
    # writes log.jsonl; PostgresStore INSERTs into zee_events and pg_notifies.
    try:
        store.append_event(
            LogEvent(
                uuid=zee_uuid,
                ts=created,
                action="created",
                actor_model=args.model,
                session_id=args.session_id,
                skill=args.skill,
                note=None,
            ),
            user_id=user_id,
        )
    except Exception as e:
        print(f"warning: event append failed: {e}", file=sys.stderr)
        print(str(target))
        return 4

    print(str(target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
