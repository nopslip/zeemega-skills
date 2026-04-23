"""Tests for lib/store.py — LocalMarkdownStore round-trips."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import log  # noqa: E402
from lib.store import (  # noqa: E402
    LocalMarkdownStore,
    LogEvent,
    PostgresStore,
    SlugCollisionError,
    Zee,
    get_store,
)


def _zee(**overrides) -> Zee:
    base = dict(
        uuid="11111111-2222-3333-4444-555555555555",
        user_id="u_local",
        title="Hello world",
        body="# Hi\n\nbody text.\n",
        created="2026-04-22T10:00:00",
        zone="tools",
        tags=["alpha", "beta"],
        what="Some what.",
        why="Some why.",
        type="note",
        model="claude-opus-4-7",
        skill="test-skill",
    )
    base.update(overrides)
    return Zee(**base)


class LocalStoreRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data_dir = self.tmp / "data"
        self.log_path = self.tmp / "log.jsonl"
        self.store = LocalMarkdownStore(
            data_dir=self.data_dir, log_path=self.log_path
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_put_then_get(self):
        z = _zee()
        fname = self.store.put(z)
        self.assertTrue(fname.endswith(".md"))
        fetched = self.store.get(z.uuid, user_id="u_local")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.uuid, z.uuid)
        self.assertEqual(fetched.title, z.title)
        self.assertEqual(fetched.tags, z.tags)
        self.assertEqual(fetched.zone, z.zone)
        self.assertIn("body text", fetched.body)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get("nope", user_id="u_local"))

    def test_put_colon_in_prose_preserved(self):
        z = _zee(
            title="Key finding migration gap",
            what="Note: the migration is the gap, not the feature.",
            why="Example: this matters because :: patterns confuse YAML.",
        )
        self.store.put(z)
        fetched = self.store.get(z.uuid, user_id="u_local")
        self.assertEqual(fetched.what, z.what)
        self.assertEqual(fetched.why, z.why)

    def test_put_upsert_same_uuid(self):
        z1 = _zee(title="First title", tags=["a"])
        self.store.put(z1)
        z2 = _zee(title="Second title", tags=["a", "b"])  # same uuid
        self.store.put(z2)
        listing = self.store.list(user_id="u_local")
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0].title, "Second title")
        self.assertEqual(listing[0].tags, ["a", "b"])

    def test_put_collision_different_uuid_raises(self):
        # Same title + created → same filename, but different uuid → collision.
        z1 = _zee()
        self.store.put(z1)
        z2 = _zee(uuid="99999999-aaaa-bbbb-cccc-dddddddddddd")
        with self.assertRaises(SlugCollisionError):
            self.store.put(z2)

    def test_list_filters(self):
        self.store.put(_zee(
            uuid="aaaaaaaa-0000-0000-0000-000000000001",
            title="Zone tools one", zone="tools", tags=["x"],
            created="2026-04-22T10:00:00",
        ))
        self.store.put(_zee(
            uuid="aaaaaaaa-0000-0000-0000-000000000002",
            title="Zone life one", zone="life", tags=["y"],
            created="2026-04-22T11:00:00",
        ))
        self.store.put(_zee(
            uuid="aaaaaaaa-0000-0000-0000-000000000003",
            title="Zone tools two", zone="tools", tags=["y", "z"],
            created="2026-04-22T12:00:00",
        ))

        tools = self.store.list(user_id="u_local", zone="tools")
        self.assertEqual({z.uuid[-1] for z in tools}, {"1", "3"})

        tagged_y = self.store.list(user_id="u_local", tag="y")
        self.assertEqual({z.uuid[-1] for z in tagged_y}, {"2", "3"})

        limited = self.store.list(user_id="u_local", limit=2)
        self.assertEqual(len(limited), 2)
        # Default sort: newest first
        self.assertEqual(limited[0].created, "2026-04-22T12:00:00")

    def test_delete(self):
        z = _zee()
        self.store.put(z)
        self.store.delete(z.uuid, user_id="u_local")
        self.assertIsNone(self.store.get(z.uuid, user_id="u_local"))
        # Deleting missing is a no-op
        self.store.delete("nope", user_id="u_local")

    def test_event_round_trip(self):
        z = _zee()
        self.store.put(z)
        self.store.append_event(
            LogEvent(
                uuid=z.uuid,
                ts="2026-04-22T10:00:00",
                action="created",
                actor_model="claude-opus-4-7",
                skill="test-skill",
            ),
            user_id="u_local",
        )
        self.store.append_event(
            LogEvent(
                uuid=z.uuid,
                ts="2026-04-22T10:05:00",
                action="edited",
                note="fixed tag",
            ),
            user_id="u_local",
        )
        events = self.store.events_for(z.uuid, user_id="u_local")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].action, "created")
        self.assertEqual(events[1].action, "edited")
        self.assertEqual(events[1].note, "fixed tag")


class PostgresStoreInit(unittest.TestCase):
    def test_requires_dsn(self):
        import os
        saved = os.environ.pop("DATABASE_URL", None)
        try:
            with self.assertRaises(RuntimeError):
                PostgresStore()
        finally:
            if saved is not None:
                os.environ["DATABASE_URL"] = saved


class FactoryTests(unittest.TestCase):
    def test_local_default(self):
        import os
        saved = os.environ.pop("ZEEMAP_STORE", None)
        try:
            self.assertIsInstance(get_store(), LocalMarkdownStore)
        finally:
            if saved is not None:
                os.environ["ZEEMAP_STORE"] = saved

    def test_unknown_raises(self):
        import os
        os.environ["ZEEMAP_STORE"] = "sqlite"
        try:
            with self.assertRaises(ValueError):
                get_store()
        finally:
            os.environ.pop("ZEEMAP_STORE", None)


if __name__ == "__main__":
    unittest.main()
