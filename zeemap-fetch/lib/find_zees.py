#!/home/dev/.hermes/hermes-agent/venv/bin/python
"""Search a user's zees and emit up to 5 candidates as JSON.

Usage:
  find_zees.py <query>

Reads DATABASE_URL, CLERK_USER_ID, and (optional) ZEEMEGA_VIEWER_URL
from the environment. Mirrors write_zee.py's exit-6 guard so silent
fallback to a missing PG connection isn't possible.

Exit codes:
  0 success
  2 bad CLI input
  5 CLERK_USER_ID not set
  6 psycopg_pool missing (no recoverable venv)
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

EXIT_BAD_INPUT = 2
EXIT_NO_USER = 5
EXIT_NO_PSYCOPG = 6

VIEWER_URL_DEFAULT = "https://app.zeemega.com"
SNIPPET_LEN = 120
LIMIT = 5


def _ensure_psycopg_pool_available() -> None:
    """Mirror write_zee.py's exit-6 guard.

    Tries to import psycopg_pool in the current interpreter. On failure,
    re-execs under a discovered hermes venv if possible, else exits 6.
    """
    try:
        import psycopg_pool  # noqa: F401
        return
    except ImportError:
        pass
    candidates = [
        os.environ.get("VIRTUAL_ENV"),
        os.environ.get("HERMES_HOME"),
        "/opt/hermes/.venv",
        str(Path.home() / ".hermes" / "hermes-agent" / "venv"),
    ]
    for base in candidates:
        if not base:
            continue
        py = Path(base) / "bin" / "python"
        if not py.is_file():
            continue
        import subprocess
        check = subprocess.run([str(py), "-c", "import psycopg_pool"])
        if check.returncode == 0:
            os.execv(str(py), [str(py), __file__, *sys.argv[1:]])
    print(
        "error: psycopg_pool unavailable in this interpreter and no recoverable hermes venv has it.",
        file=sys.stderr,
    )
    sys.exit(EXIT_NO_PSYCOPG)


def _build_filename(created_iso: str, title: str) -> str:
    """Match write_zee.py / store.ts: YYYY-MM-DD-HHMM-<slug>."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})", str(created_iso))
    if not m:
        return ""
    y, mo, d, hh, mm = m.groups()
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = "-".join([w for w in slug.split("-") if w][:5])
    return f"{y}-{mo}-{d}-{hh}{mm}-{slug}"


def _snippet(body: str, n: int = SNIPPET_LEN) -> str:
    text = re.sub(r"\s+", " ", body or "").strip()
    return text[:n] + ("..." if len(text) > n else "")


def _resolve_user_id(database_url: str, clerk_user_id: str) -> str:
    """Translate Clerk subject -> internal users.id (UUID)."""
    import psycopg
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE clerk_id = %s", (clerk_user_id,))
            row = cur.fetchone()
            if not row:
                print(
                    f"error: no users row for clerk_id={clerk_user_id!r}",
                    file=sys.stderr,
                )
                sys.exit(EXIT_NO_USER)
            return str(row[0])


def search(database_url: str, internal_user_id: str, query: str) -> list[dict]:
    import psycopg
    sql = """
        SELECT
          uuid, title, zone, type, tags, created, visibility, what, body,
          CASE
            WHEN lower(title) = lower(%(q)s)                            THEN 0
            WHEN lower(title) LIKE lower(%(q)s) || '%%'                 THEN 1
            WHEN lower(title) LIKE '%%' || lower(%(q)s) || '%%'         THEN 2
            WHEN %(q)s = ANY (tags)                                     THEN 3
            WHEN lower(zone)  = lower(%(q)s)                            THEN 4
            WHEN lower(body)  LIKE '%%' || lower(%(q)s) || '%%'         THEN 5
            ELSE 6
          END AS rank
        FROM zees
        WHERE user_id = %(uid)s::uuid
          AND (
                lower(title) LIKE '%%' || lower(%(q)s) || '%%'
             OR lower(zone)  LIKE '%%' || lower(%(q)s) || '%%'
             OR lower(body)  LIKE '%%' || lower(%(q)s) || '%%'
             OR %(q)s = ANY (tags)
          )
        ORDER BY rank ASC, created DESC
        LIMIT %(limit)s
    """
    out: list[dict] = []
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"q": query, "uid": internal_user_id, "limit": LIMIT})
            for row in cur.fetchall():
                (uuid, title, zone, type_, tags, created, visibility,
                 what, body, _rank) = row
                out.append({
                    "uuid": str(uuid),
                    "title": title,
                    "zone": zone,
                    "type": type_,
                    "tags": list(tags or []),
                    "created": created.isoformat(timespec="seconds")
                                if hasattr(created, "isoformat") else str(created),
                    "visibility": visibility,
                    "what": what,
                    "body": body or "",
                })
    return out


def to_match(row: dict, viewer_url: str) -> dict:
    filename = _build_filename(row["created"], row["title"])
    in_app = f"{viewer_url}/#/z/{urllib.parse.quote(filename)}" if filename else None
    public = (
        f"{viewer_url}/p/{urllib.parse.quote(filename)}"
        if filename and row["visibility"] in ("unlisted", "public")
        else None
    )
    return {
        "uuid": row["uuid"],
        "filename": filename,
        "title": row["title"],
        "zone": row["zone"],
        "type": row["type"],
        "tags": row["tags"],
        "created": row["created"],
        "visibility": row["visibility"],
        "what": row["what"],
        "snippet": _snippet(row["body"]),
        "in_app_url": in_app,
        "public_url": public,
    }


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print("usage: find_zees.py <query>", file=sys.stderr)
        return EXIT_BAD_INPUT
    query = sys.argv[1].strip()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("error: DATABASE_URL not set", file=sys.stderr)
        return EXIT_NO_USER  # treated as a config-missing error

    clerk_user_id = (
        os.environ.get("HERMES_OWNER_ID")
        or os.environ.get("CLERK_USER_ID")
    )
    if not clerk_user_id:
        print("error: HERMES_OWNER_ID or CLERK_USER_ID must be set", file=sys.stderr)
        return EXIT_NO_USER

    viewer_url = os.environ.get("ZEEMEGA_VIEWER_URL", VIEWER_URL_DEFAULT).rstrip("/")

    _ensure_psycopg_pool_available()

    internal_user_id = _resolve_user_id(database_url, clerk_user_id)
    rows = search(database_url, internal_user_id, query)
    matches = [to_match(r, viewer_url) for r in rows]
    json.dump({"query": query, "matches": matches}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
