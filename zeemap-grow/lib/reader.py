"""Parent-zee reader — wraps zeemap.lib.store.ZeeStore.

Resolves an identifier (uuid OR slug-style filename without .md) to a
parent zee dict via ZeeStore.get(). Handles both local and hosted modes
because ZeeStore does.
"""

from __future__ import annotations

import os
import sys
import uuid as _uuid
from pathlib import Path

# Make zeemap's lib importable. The repo install puts zeemap at
# $HERMES_HOME/skills/productivity/zeemap, so the live install during a
# user-local run looks here. For tests-from-the-repo, this same path
# resolves through the rsync'd local install once Phase E is done.
HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
ZEEMAP_LIB_PARENT = HERMES_HOME / "skills" / "productivity" / "zeemap"
if str(ZEEMAP_LIB_PARENT) not in sys.path:
    sys.path.insert(0, str(ZEEMAP_LIB_PARENT))

from lib import store  # noqa: E402


def _looks_like_uuid(s: str) -> bool:
    try:
        _uuid.UUID(s)
        return True
    except ValueError:
        return False


def _resolve_user_id() -> str:
    clerk_id = os.environ.get("CLERK_USER_ID")
    if not clerk_id:
        raise RuntimeError(
            "CLERK_USER_ID not set; zeemap-grow needs it to read your zees"
        )
    s = store.get_store()
    return s.resolve_user(clerk_id)


def get_parent(identifier: str) -> dict:
    """Look up a parent zee by uuid or slug-style filename.

    Returns a flat dict matching the shape the dispatcher and prompt
    renderer expect: uuid, title, type, zone, tags, what, why, body.

    Raises LookupError if not found.
    """
    s = store.get_store()
    user_id = _resolve_user_id()

    if _looks_like_uuid(identifier):
        zee = s.get(identifier, user_id=user_id)
    else:
        # Slug-style: search the user's list for a matching filename or
        # title. Slug is "YYYY-MM-DD-HHMM-<slug>" (no .md). Match against
        # the canonical filename derived from `created` + `title`.
        candidates = s.list(user_id=user_id)
        zee = next(
            (
                z for z in candidates
                if _slug_matches(z, identifier)
            ),
            None,
        )

    if zee is None:
        raise LookupError(f"no zee found for identifier: {identifier!r}")

    return _to_dict(zee)


def _slug_matches(zee, identifier: str) -> bool:
    # Canonical slug: YYYY-MM-DD-HHMM-title-slug
    created = (zee.created or "")[:16].replace("T", "-").replace(":", "")
    if not created:
        return False
    title_slug = "-".join(
        ch for ch in zee.title.lower().replace(" ", "-")
        if ch.isalnum() or ch == "-"
    )
    canonical = f"{created[:10]}-{created[11:15]}-{title_slug}"
    return canonical.startswith(identifier) or identifier in canonical


def _to_dict(zee) -> dict:
    return {
        "uuid": zee.uuid,
        "title": zee.title,
        "type": zee.type or "seed",
        "zone": zee.zone or "uncategorized",
        "tags": list(zee.tags or []),
        "what": zee.what or "",
        "why": zee.why or "",
        "body": zee.body or "",
    }
