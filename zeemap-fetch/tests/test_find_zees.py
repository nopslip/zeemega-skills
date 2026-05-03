"""Tests for find_zees.py.

Pure-function tests are unit; the search() function is covered by an
opt-in integration test that requires DATABASE_URL + CLERK_USER_ID.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

import find_zees  # noqa: E402


def test_build_filename_uses_minute_precision():
    fn = find_zees._build_filename("2026-04-22T09:00:00", "La Garita property notes")
    assert fn == "2026-04-22-0900-la-garita-property-notes"


def test_build_filename_handles_space_separator():
    assert (
        find_zees._build_filename("2026-04-22 09:00:00", "Hello World")
        == "2026-04-22-0900-hello-world"
    )


def test_build_filename_returns_empty_for_bad_iso():
    assert find_zees._build_filename("nope", "Hello") == ""


def test_snippet_collapses_whitespace_and_truncates():
    body = "Hello\n\nworld " * 50
    s = find_zees._snippet(body, n=20)
    assert len(s) <= 20 + 3  # +ellipsis
    assert "\n" not in s


def test_to_match_sets_public_url_when_unlisted():
    row = {
        "uuid": "x",
        "title": "Hello",
        "zone": "tools",
        "type": "note",
        "tags": ["a"],
        "created": "2026-04-22T09:00:00",
        "visibility": "unlisted",
        "what": "what",
        "body": "body",
    }
    m = find_zees.to_match(row, "https://app.zeemega.com")
    assert m["public_url"] == "https://app.zeemega.com/p/2026-04-22-0900-hello"
    assert m["in_app_url"] == "https://app.zeemega.com/#/z/2026-04-22-0900-hello"


def test_to_match_omits_public_url_when_private():
    row = {
        "uuid": "x",
        "title": "Hello",
        "zone": None,
        "type": None,
        "tags": [],
        "created": "2026-04-22T09:00:00",
        "visibility": "private",
        "what": None,
        "body": "",
    }
    m = find_zees.to_match(row, "https://app.zeemega.com")
    assert m["public_url"] is None
    assert m["in_app_url"] is not None


def test_cli_missing_query_exits_2():
    cmd = [sys.executable, str(REPO_ROOT / "lib" / "find_zees.py")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 2
    assert "usage" in r.stderr


def _run_cli(env: dict, *args: str) -> subprocess.CompletedProcess:
    """Invoke the CLI with a controlled env (no inherit). DATABASE_URL is
    set to a non-empty placeholder so the script doesn't bail at the
    DATABASE_URL check; we want to exercise the owner-id validation
    layer that runs before any DB connection is attempted."""
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "lib" / "find_zees.py"), *args],
        capture_output=True, text=True, env=env,
    )


def test_cli_invalid_hermes_owner_id_exits_5():
    env = {
        "PATH": os.environ.get("PATH", ""),
        "DATABASE_URL": "postgresql://placeholder/none",
        "HERMES_OWNER_ID": "user_3CowcZfslxmetPVhIXDwX8uqaNu",  # Clerk subject, not a UUID
    }
    r = _run_cli(env, "zee")
    assert r.returncode == 5, r.stderr
    assert "must be a UUID" in r.stderr


def test_cli_clerk_user_id_that_is_a_uuid_exits_5():
    env = {
        "PATH": os.environ.get("PATH", ""),
        "DATABASE_URL": "postgresql://placeholder/none",
        "CLERK_USER_ID": "393b9f12-3d18-49e7-9215-b5704af79b79",
    }
    r = _run_cli(env, "zee")
    assert r.returncode == 5, r.stderr
    assert "looks like a UUID" in r.stderr


def test_cli_neither_owner_var_set_exits_5():
    env = {
        "PATH": os.environ.get("PATH", ""),
        "DATABASE_URL": "postgresql://placeholder/none",
    }
    r = _run_cli(env, "zee")
    assert r.returncode == 5, r.stderr
    assert "HERMES_OWNER_ID or CLERK_USER_ID" in r.stderr


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL") or not os.environ.get("CLERK_USER_ID"),
    reason="integration test needs DATABASE_URL + CLERK_USER_ID",
)
def test_cli_returns_json_with_matches_array():
    env = {**os.environ, "ZEEMEGA_VIEWER_URL": "https://app.zeemega.com"}
    r = subprocess.run(
        [sys.executable, str(REPO_ROOT / "lib" / "find_zees.py"), "zee"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["query"] == "zee"
    assert isinstance(payload["matches"], list)
