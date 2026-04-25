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
  6 — postgres required but unavailable (psycopg_pool missing and no
      venv recoverable), OR DATABASE_URL set but ZEEMAP_STORE=local
      (agent silent-fallback guard). Do NOT retry with
      ZEEMAP_STORE=local — surface this error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
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


def _find_venv_python_with_psycopg_pool() -> str | None:
    """Locate a python interpreter that has psycopg_pool available.

    Order: $VIRTUAL_ENV, $HERMES_HOME/hermes-agent/venv, /opt/hermes/.venv
    (kids container layout), ~/.hermes/hermes-agent/venv (host layout).
    Returns None if none work. Never returns the current interpreter
    (caller only calls this when the current interpreter lacks psycopg_pool).
    """
    candidates: list[Path] = []
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        candidates.append(Path(venv) / "bin" / "python")
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        candidates.append(Path(hermes_home) / "hermes-agent" / "venv" / "bin" / "python")
    candidates.extend([
        Path("/opt/hermes/.venv/bin/python"),
        Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python",
    ])
    current = Path(sys.executable).resolve()
    seen: set[Path] = set()
    for p in candidates:
        try:
            resolved = p.resolve()
        except OSError:
            continue
        if resolved in seen or resolved == current:
            continue
        seen.add(resolved)
        if not p.exists():
            continue
        try:
            r = subprocess.run(
                [str(p), "-c", "import psycopg_pool"],
                capture_output=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0:
            return str(p)
    return None


def _guard_postgres_backend(backend: str) -> None:
    """Refuse the two silent-data-loss paths before we touch the store.

    1. DATABASE_URL set + ZEEMAP_STORE=local → the caller is bypassing
       Postgres. Silent local writes never reach the viewer.
    2. ZEEMAP_STORE=postgres + psycopg_pool unimportable in the current
       interpreter → re-exec under a venv python that has it; if none
       exists, exit loudly rather than let PostgresStore crash and
       tempt the caller into ZEEMAP_STORE=local as a "fix".
    """
    if backend == "local" and os.environ.get("DATABASE_URL"):
        print(
            "error: DATABASE_URL is set but ZEEMAP_STORE=local — refusing "
            "to silently bypass Postgres. If Postgres is erroring, surface "
            "the real error to the user instead of forcing local mode. "
            "To genuinely run in local mode, unset DATABASE_URL.",
            file=sys.stderr,
        )
        sys.exit(6)
    if backend != "postgres":
        return
    try:
        import psycopg_pool  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    venv_py = _find_venv_python_with_psycopg_pool()
    if venv_py:
        script = str(Path(__file__).resolve())
        os.execv(venv_py, [venv_py, script, *sys.argv[1:]])
    print(
        f"error: ZEEMAP_STORE=postgres requires psycopg_pool, but the "
        f"current interpreter ({sys.executable}) does not have it and "
        f"no hermes venv with it was found. Do NOT retry with "
        f"ZEEMAP_STORE=local — that silently bypasses the database. "
        f"Install psycopg_pool into this interpreter, or invoke "
        f"write_zee.py via the hermes venv python directly.",
        file=sys.stderr,
    )
    sys.exit(6)


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
    # May os.execv under a venv python; if it does, we don't return here.
    _guard_postgres_backend(backend)
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
