"""Tests for lib/reader._resolve_user_id.

Boundary validation for HERMES_OWNER_ID / CLERK_USER_ID. The full DB
round-trip is covered by integration tests; here we just verify the
env-var precedence and validation rules.
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

import reader  # noqa: E402


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("HERMES_OWNER_ID", raising=False)
    monkeypatch.delenv("CLERK_USER_ID", raising=False)
    return monkeypatch


def test_hermes_owner_id_returned_directly(clean_env):
    """When HERMES_OWNER_ID is a valid UUID, return it without a DB call."""
    owner = "393b9f12-3d18-49e7-9215-b5704af79b79"
    clean_env.setenv("HERMES_OWNER_ID", owner)
    # If reader tried to talk to the DB this would explode (no
    # DATABASE_URL). The fact that it returns cleanly proves no resolve.
    assert reader._resolve_user_id() == owner


def test_hermes_owner_id_rejects_non_uuid(clean_env):
    clean_env.setenv("HERMES_OWNER_ID", "user_3CowcZfslxmetPVhIXDwX8uqaNu")
    with pytest.raises(RuntimeError, match="must be a UUID"):
        reader._resolve_user_id()


def test_clerk_user_id_rejects_uuid(clean_env):
    clean_env.setenv("CLERK_USER_ID", "393b9f12-3d18-49e7-9215-b5704af79b79")
    with pytest.raises(RuntimeError, match="looks like a UUID"):
        reader._resolve_user_id()


def test_neither_set_raises(clean_env):
    with pytest.raises(RuntimeError, match="HERMES_OWNER_ID"):
        reader._resolve_user_id()


def test_clerk_fallback_calls_resolve_user(clean_env, monkeypatch, capsys):
    """When only CLERK_USER_ID is set, fall back to store.resolve_user
    and emit a deprecation warning to stderr."""
    clean_env.setenv("CLERK_USER_ID", "user_3CowcZfslxmetPVhIXDwX8uqaNu")
    captured = {}

    class FakeStore:
        def resolve_user(self, clerk_id, email=None):
            captured["clerk_id"] = clerk_id
            return "393b9f12-3d18-49e7-9215-b5704af79b79"

    monkeypatch.setattr(reader.store, "get_store", lambda: FakeStore())
    result = reader._resolve_user_id()
    assert result == "393b9f12-3d18-49e7-9215-b5704af79b79"
    assert captured["clerk_id"] == "user_3CowcZfslxmetPVhIXDwX8uqaNu"
    err = capsys.readouterr().err
    assert "CLERK_USER_ID is deprecated" in err
