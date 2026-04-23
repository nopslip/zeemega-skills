"""Tests for lib/log.py — run with: python3 -m unittest tests/test_log.py"""

from __future__ import annotations

import json
import multiprocessing
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import log  # noqa: E402


def _appender(args):
    path, uuid, n, worker_id = args
    for i in range(n):
        log.append(
            {
                "uuid": uuid,
                "ts": f"2026-04-19T12:00:{i:02d}",
                "action": "edited",
                "actor_model": f"worker-{worker_id}",
                "skill": "test",
                "note": f"worker {worker_id} event {i}",
            },
            path=path,
        )


class TestLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = Path(self.tmp) / "log.jsonl"

    def tearDown(self):
        if self.path.exists():
            self.path.unlink()
        os.rmdir(self.tmp)

    def test_append_and_read_roundtrip(self):
        ev = {
            "uuid": "a1b2",
            "ts": "2026-04-19T12:00:00",
            "action": "created",
            "actor_model": "claude-opus-4-7",
            "skill": "zeemap",
            "note": "first",
        }
        log.append(ev, path=self.path)
        events = log.events_for("a1b2", path=self.path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["note"], "first")
        self.assertEqual(events[0]["action"], "created")

    def test_missing_required_field_raises(self):
        with self.assertRaises(ValueError):
            log.append({"uuid": "x", "ts": "2026-04-19T12:00:00"}, path=self.path)

    def test_unknown_action_raises(self):
        with self.assertRaises(ValueError):
            log.append(
                {"uuid": "x", "ts": "2026-04-19T12:00:00", "action": "teleported"},
                path=self.path,
            )

    def test_oversize_event_raises(self):
        big_note = "x" * 5000
        with self.assertRaises(ValueError):
            log.append(
                {
                    "uuid": "x",
                    "ts": "2026-04-19T12:00:00",
                    "action": "edited",
                    "note": big_note,
                },
                path=self.path,
            )

    def test_events_for_filters_by_uuid(self):
        for u in ("a", "b", "a", "c", "a"):
            log.append(
                {"uuid": u, "ts": "2026-04-19T12:00:00", "action": "edited"},
                path=self.path,
            )
        self.assertEqual(len(log.events_for("a", path=self.path)), 3)
        self.assertEqual(len(log.events_for("b", path=self.path)), 1)
        self.assertEqual(len(log.events_for("zzz", path=self.path)), 0)

    def test_summary_shape(self):
        events = [
            {"uuid": "u", "ts": "2026-04-19T12:00:00", "action": "created",
             "actor_model": "claude-opus-4-7", "skill": "zeemap"},
            {"uuid": "u", "ts": "2026-04-19T13:00:00", "action": "edited",
             "actor_model": "claude-haiku-4-5", "skill": "zeemap-audit"},
            {"uuid": "u", "ts": "2026-04-19T14:00:00", "action": "tagged",
             "actor_model": "claude-haiku-4-5", "skill": "zeemap-audit"},
        ]
        for e in events:
            log.append(e, path=self.path)
        s = log.summary("u", path=self.path)
        self.assertEqual(s["edits"], 2)  # edited + tagged
        self.assertEqual(s["last_touched"], "2026-04-19T14:00:00")
        self.assertEqual(sorted(s["models_touched"]),
                         ["claude-haiku-4-5", "claude-opus-4-7"])
        self.assertEqual(sorted(s["skills_touched"]),
                         ["zeemap", "zeemap-audit"])
        self.assertEqual(s["actions"], {"created": 1, "edited": 1, "tagged": 1})

    def test_summary_empty(self):
        s = log.summary("nonexistent", path=self.path)
        self.assertEqual(s["edits"], 0)
        self.assertIsNone(s["last_touched"])

    def test_recent_reverses_and_caps(self):
        for i in range(10):
            log.append(
                {"uuid": f"u{i}", "ts": f"2026-04-19T12:00:{i:02d}",
                 "action": "created"},
                path=self.path,
            )
        r = log.recent(3, path=self.path)
        self.assertEqual(len(r), 3)
        self.assertEqual(r[0]["uuid"], "u9")  # most recent first
        self.assertEqual(r[2]["uuid"], "u7")

    def test_concurrent_append_no_interleaving(self):
        """Two worker processes append in parallel; no line should be corrupted."""
        n_per_worker = 200
        with multiprocessing.Pool(4) as pool:
            pool.map(
                _appender,
                [(str(self.path), "shared", n_per_worker, i) for i in range(4)],
            )

        # Every line must parse as valid JSON.
        with self.path.open() as f:
            lines = [line for line in f if line.strip()]

        self.assertEqual(len(lines), 4 * n_per_worker)
        for line in lines:
            event = json.loads(line)  # would raise on any interleaving
            self.assertEqual(event["uuid"], "shared")
            self.assertEqual(event["action"], "edited")

    def test_corrupt_line_is_skipped(self):
        log.append(
            {"uuid": "a", "ts": "2026-04-19T12:00:00", "action": "created"},
            path=self.path,
        )
        # Simulate a partial/corrupt line sneaking in.
        with self.path.open("a") as f:
            f.write("not-json-at-all\n")
        log.append(
            {"uuid": "b", "ts": "2026-04-19T12:00:01", "action": "created"},
            path=self.path,
        )
        events = list(log._iter_all(path=self.path))
        self.assertEqual(len(events), 2)  # corrupt line skipped


if __name__ == "__main__":
    unittest.main()
