"""ZeeStore — storage abstraction for the zeemap skill.

Two implementations:

- LocalMarkdownStore: writes .md files to ZEEMAP_DATA_DIR + appends to
  log.jsonl. Wraps today's behavior. Default.
- PostgresStore: writes rows to the `zees` / `zee_events` tables, issues
  `pg_notify('zees:' || user_id, uuid)` on every write. Selected via
  ZEEMAP_STORE=postgres. Requires DATABASE_URL. Threads user_id through.

`user_id` in this module is the INTERNAL users.id UUID, not the Clerk
subject. Callers (write_zee, migrate_to_postgres, audit) convert their
CLERK_USER_ID env var to an internal UUID once via
`store.resolve_user(clerk_id)` at startup and cache the result. That
keeps Clerk out of the data layer entirely — swapping auth providers
later is an ALTER TABLE on `users`, not a rewrite of every zee row.

Callers get a store via get_store(); both write_zee.py and zeemap-audit
will route through this.
"""

from __future__ import annotations

import datetime as _dt
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from lib import log, write_zee

DEFAULT_DATA_DIR = Path.home() / ".hermes" / "skills" / "productivity" / "zeemap" / "data"


class SlugCollisionError(Exception):
    """Raised when a put() would overwrite an unrelated zee at the same path."""


@dataclass
class Zee:
    uuid: str
    user_id: str
    title: str
    body: str
    created: str                  # ISO-8601
    zone: str | None = None
    tags: list[str] = field(default_factory=list)
    what: str | None = None
    why: str | None = None
    schema_version: int = 1
    updated: str | None = None
    type: str | None = None
    model: str | None = None
    skill: str | None = None
    skill_url: str | None = None
    seeded_from: list[str] = field(default_factory=list)


@dataclass
class LogEvent:
    uuid: str                     # zee uuid (or sentinel for system events)
    ts: str                       # ISO-8601
    action: str                   # must be in log.py KNOWN_ACTIONS
    actor_model: str | None = None
    session_id: str | None = None
    skill: str | None = None
    note: str | None = None


class ZeeStore(ABC):
    @abstractmethod
    def put(self, zee: Zee) -> str:
        """Insert or overwrite a zee. Returns backend-specific identifier
        (filename for Local, uuid for Postgres). Upsert by uuid."""

    @abstractmethod
    def get(self, uuid: str, *, user_id: str) -> Zee | None:
        """Fetch a single zee. Returns None if absent or cross-user."""

    @abstractmethod
    def list(self, *, user_id: str, **filters) -> list[Zee]:
        """List zees for a user. Filters: zone=..., tag=..., limit=..."""

    @abstractmethod
    def delete(self, uuid: str, *, user_id: str) -> None:
        """Hard-delete. Soft-delete is modeled via 'hidden' events, not here."""

    @abstractmethod
    def append_event(self, event: LogEvent, *, user_id: str) -> None:
        """Append one lifecycle event. Atomic per event."""

    @abstractmethod
    def events_for(self, uuid: str, *, user_id: str) -> Iterable[LogEvent]:
        """All events for a zee, oldest first."""

    @abstractmethod
    def resolve_user(self, clerk_id: str, email: str | None = None) -> str:
        """Map an auth-provider identifier (today: Clerk user_id) to the
        internal users.id used as the isolation boundary. Local mode has
        no users table and returns clerk_id unchanged. Postgres mode
        upserts the users row and returns the UUID."""


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Empty dict if no frontmatter."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text
    head = parts[0]
    body = parts[1].lstrip("\n")
    head_yaml = head[len("---"):].lstrip("\n")
    try:
        data = yaml.safe_load(head_yaml) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(data, dict):
        return {}, text
    return data, body


def _as_iso(value) -> str | None:
    """YAML may deserialize timestamps as datetime; normalize back to ISO-8601."""
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, _dt.date):
        return value.isoformat()
    return str(value)


_FILENAME_TS_RE = __import__("re").compile(
    r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})-"
)


def _created_from_filename(path: Path) -> str | None:
    """V0 zees have only `date: YYYY-MM-DD` in frontmatter. The filename
    itself (`YYYY-MM-DD-HHMM-slug.md`) carries the precise timestamp we
    want in `created`. Returns None if the filename doesn't match."""
    m = _FILENAME_TS_RE.match(path.name)
    if not m:
        return None
    y, mo, d, hh, mm = m.groups()
    return f"{y}-{mo}-{d}T{hh}:{mm}:00"


def _zee_from_file(path: Path, user_id: str) -> Zee | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm, body = _split_frontmatter(text)
    if not fm or "uuid" not in fm:
        return None
    # Fallback chain for `created`: created → date → filename timestamp.
    # Matches the viewer's getEffectiveCreated behavior so v0 zees
    # (which only have `date:`) migrate and render with real timestamps.
    created = (
        _as_iso(fm.get("created"))
        or _as_iso(fm.get("date"))
        or _created_from_filename(path)
        or ""
    )
    return Zee(
        uuid=str(fm["uuid"]),
        user_id=user_id,
        title=str(fm.get("title", "")),
        body=body,
        created=created,
        zone=fm.get("zone"),
        tags=list(fm.get("tags") or []),
        what=fm.get("what"),
        why=fm.get("why"),
        schema_version=int(fm.get("schema_version", 1)),
        updated=_as_iso(fm.get("updated")),
        type=fm.get("type"),
        model=fm.get("model"),
        skill=fm.get("skill"),
        skill_url=fm.get("skill_url"),
        seeded_from=list(fm.get("seeded_from") or []),
    )


class LocalMarkdownStore(ZeeStore):
    """Markdown-files-on-disk + log.jsonl. Single-user local setup.

    user_id is accepted but ignored in the current local layout — there
    is no per-user dir yet. It's threaded through the signature so the
    callers don't need to branch on backend.
    """

    def __init__(
        self,
        data_dir: Path | str | None = None,
        log_path: Path | str | None = None,
    ):
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        else:
            env_dir = os.environ.get("ZEEMAP_DATA_DIR")
            self.data_dir = Path(env_dir) if env_dir else DEFAULT_DATA_DIR
        self.log_path = Path(log_path) if log_path is not None else None

    def _find_path_by_uuid(self, uuid: str) -> Path | None:
        if not self.data_dir.exists():
            return None
        for p in self.data_dir.glob("*.md"):
            z = _zee_from_file(p, user_id="")
            if z and z.uuid == uuid:
                return p
        return None

    def put(self, zee: Zee) -> str:
        fields = {
            "created": zee.created,
            "type": zee.type or "note",
            "zone": zee.zone or "",
            "title": zee.title,
            "tags": list(zee.tags),
            "what": zee.what or "",
            "why": zee.why or "",
            "uuid": zee.uuid,
            "schema_version": zee.schema_version,
            "model": zee.model,
            "skill": zee.skill,
            "skill_url": zee.skill_url,
            "seeded_from": list(zee.seeded_from),
        }
        frontmatter = write_zee.build_frontmatter(fields)
        filename = write_zee.build_filename(zee.created, zee.title)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        target = self.data_dir / filename

        existing_path = self._find_path_by_uuid(zee.uuid)
        if existing_path is not None and existing_path != target:
            existing_path.unlink()

        if target.exists() and existing_path != target:
            other = _zee_from_file(target, user_id=zee.user_id)
            if other is None:
                # Unrecognized file at the target path — don't clobber it.
                raise SlugCollisionError(
                    f"target {target.name} already exists and isn't a zee we know"
                )
            if other.uuid != zee.uuid:
                raise SlugCollisionError(
                    f"target {target.name} already held by uuid {other.uuid}"
                )

        body = zee.body
        document = f"---\n{frontmatter}\n---\n\n{body}"
        if not document.endswith("\n"):
            document += "\n"
        target.write_text(document, encoding="utf-8")
        return filename

    def get(self, uuid: str, *, user_id: str) -> Zee | None:
        p = self._find_path_by_uuid(uuid)
        if p is None:
            return None
        return _zee_from_file(p, user_id=user_id)

    def list(self, *, user_id: str, **filters) -> list[Zee]:
        zone = filters.get("zone")
        tag = filters.get("tag")
        limit = filters.get("limit")
        if not self.data_dir.exists():
            return []
        out: list[Zee] = []
        for p in self.data_dir.glob("*.md"):
            z = _zee_from_file(p, user_id=user_id)
            if z is None:
                continue
            if zone is not None and z.zone != zone:
                continue
            if tag is not None and tag not in z.tags:
                continue
            out.append(z)
        out.sort(key=lambda z: (z.updated or z.created or ""), reverse=True)
        if limit is not None:
            out = out[: int(limit)]
        return out

    def delete(self, uuid: str, *, user_id: str) -> None:
        p = self._find_path_by_uuid(uuid)
        if p is None:
            return
        p.unlink()

    def append_event(self, event: LogEvent, *, user_id: str) -> None:
        log.append(
            {
                "uuid": event.uuid,
                "ts": event.ts,
                "action": event.action,
                "actor_model": event.actor_model,
                "session_id": event.session_id,
                "skill": event.skill,
                "note": event.note,
            },
            path=self.log_path,
        )

    def events_for(self, uuid: str, *, user_id: str) -> list[LogEvent]:
        raw = log.events_for(uuid, path=self.log_path)
        out: list[LogEvent] = []
        for e in raw:
            out.append(LogEvent(
                uuid=e.get("uuid", ""),
                ts=e.get("ts", ""),
                action=e.get("action", ""),
                actor_model=e.get("actor_model"),
                session_id=e.get("session_id"),
                skill=e.get("skill"),
                note=e.get("note"),
            ))
        return out

    def resolve_user(self, clerk_id: str, email: str | None = None) -> str:
        # Single-user / self-host: no users table. The clerk_id (or
        # whatever the caller passed) flows through unchanged.
        return clerk_id


class PostgresStore(ZeeStore):
    """Postgres-backed store. Selected via ZEEMAP_STORE=postgres.

    Requires DATABASE_URL. Emits pg_notify('zees:' || user_id, uuid) on every
    put/append_event so the viewer's SSE stream can push to the matching
    Clerk user without polling.

    Connection policy: one short-lived connection per call via
    psycopg_pool.ConnectionPool. LISTEN subscribers open their own
    dedicated connection (not pooled) — see subscribe() on the viewer side.
    """

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.environ.get("DATABASE_URL")
        if not self.dsn:
            raise RuntimeError(
                "PostgresStore requires DATABASE_URL (or dsn=). "
                "Got neither."
            )
        # Lazy — build on first use so tests that only assert init won't
        # open sockets.
        self._pool = None
        # Clerk ID → users.id cache. Per-process; fine because the Hermes
        # container runs as one user and resolves once at startup.
        self._user_id_cache: dict[str, str] = {}

    def _get_pool(self):
        if self._pool is None:
            from psycopg_pool import ConnectionPool
            self._pool = ConnectionPool(self.dsn, min_size=0, max_size=4,
                                        open=True)
        return self._pool

    def put(self, zee: Zee) -> str:
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO zees (
                      uuid, user_id, title, zone, tags, what, why, body,
                      schema_version, created, updated, type, model, skill,
                      skill_url, seeded_from
                    ) VALUES (
                      %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, COALESCE(%s::timestamptz, now()),
                      %s, %s, %s, %s, %s::uuid[]
                    )
                    ON CONFLICT (uuid) DO UPDATE SET
                      title          = EXCLUDED.title,
                      zone           = EXCLUDED.zone,
                      tags           = EXCLUDED.tags,
                      what           = EXCLUDED.what,
                      why            = EXCLUDED.why,
                      body           = EXCLUDED.body,
                      schema_version = EXCLUDED.schema_version,
                      updated        = now(),
                      type           = EXCLUDED.type,
                      model          = EXCLUDED.model,
                      skill          = EXCLUDED.skill,
                      skill_url      = EXCLUDED.skill_url,
                      seeded_from    = EXCLUDED.seeded_from
                    """,
                    (
                        zee.uuid, zee.user_id, zee.title, zee.zone,
                        list(zee.tags), zee.what, zee.why, zee.body,
                        zee.schema_version, zee.created, zee.updated,
                        zee.type, zee.model, zee.skill, zee.skill_url,
                        list(zee.seeded_from),
                    ),
                )
                cur.execute(
                    "SELECT pg_notify('zees:' || %s, %s)",
                    (zee.user_id, zee.uuid),
                )
        return zee.uuid

    def _row_to_zee(self, row) -> Zee:
        (
            uuid, user_id, title, zone, tags, what, why, body,
            schema_version, created, updated, type_, model, skill,
            skill_url, seeded_from,
        ) = row
        return Zee(
            uuid=str(uuid),
            user_id=user_id,
            title=title,
            body=body,
            created=created.isoformat(timespec="seconds")
                if hasattr(created, "isoformat") else str(created),
            zone=zone,
            tags=list(tags or []),
            what=what,
            why=why,
            schema_version=schema_version,
            updated=updated.isoformat(timespec="seconds")
                if hasattr(updated, "isoformat") else (updated and str(updated)),
            type=type_,
            model=model,
            skill=skill,
            skill_url=skill_url,
            seeded_from=[str(u) for u in (seeded_from or [])],
        )

    _SELECT = """
        SELECT uuid, user_id, title, zone, tags, what, why, body,
               schema_version, created, updated, type, model, skill,
               skill_url, seeded_from
          FROM zees
    """

    def get(self, uuid: str, *, user_id: str) -> Zee | None:
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self._SELECT + " WHERE uuid = %s AND user_id = %s",
                    (uuid, user_id),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_zee(row)

    def list(self, *, user_id: str, **filters) -> list[Zee]:
        zone = filters.get("zone")
        tag = filters.get("tag")
        limit = filters.get("limit")
        clauses = ["user_id = %s"]
        params: list = [user_id]
        if zone is not None:
            clauses.append("zone = %s")
            params.append(zone)
        if tag is not None:
            clauses.append("%s = ANY(tags)")
            params.append(tag)
        sql = self._SELECT + " WHERE " + " AND ".join(clauses) \
            + " ORDER BY updated DESC, created DESC"
        if limit is not None:
            sql += " LIMIT %s"
            params.append(int(limit))
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [self._row_to_zee(r) for r in rows]

    def delete(self, uuid: str, *, user_id: str) -> None:
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM zees WHERE uuid = %s AND user_id = %s",
                    (uuid, user_id),
                )

    def append_event(self, event: LogEvent, *, user_id: str) -> None:
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO zee_events
                      (zee_uuid, user_id, ts, actor_model, session_id,
                       skill, action, note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event.uuid, user_id, event.ts, event.actor_model,
                        event.session_id, event.skill, event.action,
                        event.note,
                    ),
                )
                cur.execute(
                    "SELECT pg_notify('zees:' || %s, %s)",
                    (user_id, event.uuid),
                )

    def events_for(self, uuid: str, *, user_id: str) -> list[LogEvent]:
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT zee_uuid, ts, action, actor_model, session_id,
                           skill, note
                      FROM zee_events
                     WHERE zee_uuid = %s AND user_id = %s
                     ORDER BY ts, id
                    """,
                    (uuid, user_id),
                )
                rows = cur.fetchall()
        out: list[LogEvent] = []
        for r in rows:
            zee_uuid, ts, action, actor_model, session_id, skill, note = r
            out.append(LogEvent(
                uuid=str(zee_uuid),
                ts=ts.isoformat(timespec="seconds")
                    if hasattr(ts, "isoformat") else str(ts),
                action=action,
                actor_model=actor_model,
                session_id=session_id,
                skill=skill,
                note=note,
            ))
        return out

    def resolve_user(self, clerk_id: str, email: str | None = None) -> str:
        if not clerk_id:
            raise ValueError("resolve_user requires a non-empty clerk_id")
        cached = self._user_id_cache.get(clerk_id)
        if cached is not None:
            return cached
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (clerk_id, email)
                    VALUES (%s, %s)
                    ON CONFLICT (clerk_id) DO UPDATE
                      SET email = COALESCE(EXCLUDED.email, users.email)
                    RETURNING id
                    """,
                    (clerk_id, email),
                )
                row = cur.fetchone()
        if row is None:
            raise RuntimeError(
                f"resolve_user: users upsert returned no row for {clerk_id!r}"
            )
        user_id = str(row[0])
        self._user_id_cache[clerk_id] = user_id
        return user_id


def get_store() -> ZeeStore:
    """Factory — picks the adapter based on ZEEMAP_STORE env var."""
    backend = os.environ.get("ZEEMAP_STORE", "local").strip().lower()
    if backend == "local":
        return LocalMarkdownStore()
    if backend == "postgres":
        return PostgresStore()
    raise ValueError(
        f"unknown ZEEMAP_STORE={backend!r} (expected 'local' or 'postgres')"
    )
