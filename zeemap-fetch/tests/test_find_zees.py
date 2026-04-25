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
