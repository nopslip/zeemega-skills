"""UUID-only migration for existing zees (Path A).

Stamps every zee that lacks a `uuid:` frontmatter field with a v4 UUID.
NOTHING else is changed — no `schema_version:`, no `created:` rewrites,
no synthesized log events. Per execution plan Decision 4.

DEFAULT MODE IS --dry-run. --commit is required for real writes. The
execution plan gates --commit on explicit Zak go-ahead; this script does
not enforce that by itself — the human does.
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid as uuid_mod
from pathlib import Path

DEFAULT_DATA_DIR = Path.home() / ".hermes" / "skills" / "productivity" / "zeemap" / "data"
ZEE_FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-[a-z0-9-]+\.md$")
UUID_LINE_RE = re.compile(r"^uuid:\s*\S", re.MULTILINE)


def _split_frontmatter(raw: str) -> tuple[str, str, str] | None:
    """Return (head, frontmatter_body, tail) or None if no ---...--- block."""
    if not raw.startswith("---\n") and not raw.startswith("---\r\n"):
        return None
    # Find closing --- on its own line
    m = re.search(r"\n---\s*\n", raw)
    if not m:
        return None
    head = "---\n"
    start_fm = len(head)
    end_fm = m.start() + 1  # include the newline before closing ---
    fm_body = raw[start_fm:end_fm]
    tail = raw[end_fm:]  # starts with "---\n..."
    return head, fm_body, tail


def stamp_content(raw: str, new_uuid: str) -> tuple[str, str]:
    """Return (new_content, status). status in {'stamped', 'has_uuid', 'no_frontmatter'}."""
    split = _split_frontmatter(raw)
    if split is None:
        return raw, "no_frontmatter"
    head, fm_body, tail = split
    if UUID_LINE_RE.search(fm_body):
        return raw, "has_uuid"
    # Insert uuid at the end of the frontmatter block (before closing ---).
    if not fm_body.endswith("\n"):
        fm_body = fm_body + "\n"
    fm_body = fm_body + f"uuid: {new_uuid}\n"
    return head + fm_body + tail, "stamped"


def iter_zees(data_dir: Path):
    for p in sorted(data_dir.iterdir()):
        if not p.is_file():
            continue
        if not ZEE_FILENAME_RE.match(p.name):
            continue
        yield p


def run(data_dir: Path, *, commit: bool) -> dict:
    stats = {"stamped": 0, "has_uuid": 0, "no_frontmatter": 0}
    actions: list[tuple[str, str]] = []  # (status, filename)

    for path in iter_zees(data_dir):
        raw = path.read_text(encoding="utf-8")
        new_uuid = str(uuid_mod.uuid4())
        new_raw, status = stamp_content(raw, new_uuid)
        stats[status] += 1
        actions.append((status, path.name))
        if status == "stamped" and commit:
            path.write_text(new_raw, encoding="utf-8")

    return {"stats": stats, "actions": actions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument(
        "--commit", action="store_true",
        help="Actually modify files. Default is dry-run (no writes).",
    )
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir).expanduser()
    if not data_dir.is_dir():
        print(f"error: data dir not found: {data_dir}", file=sys.stderr)
        return 2

    mode = "COMMIT" if args.commit else "DRY-RUN"
    print(f"[migrate_uuid Path A, mode={mode}] scanning {data_dir}")
    result = run(data_dir, commit=args.commit)
    for status, name in result["actions"]:
        marker = {
            "stamped": "  stamp ",
            "has_uuid": "  skip  ",
            "no_frontmatter": "  skip* ",
        }[status]
        print(f"{marker} {name}")
    s = result["stats"]
    print(
        f"\nsummary: {s['stamped']} stamped, "
        f"{s['has_uuid']} skipped (already had UUID), "
        f"{s['no_frontmatter']} skipped (no frontmatter)"
    )
    if not args.commit:
        print("\n(dry-run — no files modified. Re-run with --commit to apply.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
