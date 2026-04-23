"""Tests for lib/migrate_uuid.py"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import migrate_uuid  # noqa: E402

UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


V0_SAMPLE = """---
date: 2026-04-11
type: idea
zone: garden
title: Hello garden world
tags: [garden, meta]
---

The first seed.
"""

V1_SAMPLE = """---
created: 2026-04-19T12:00:00
type: seed
zone: tech
title: "With uuid already"
tags: [x]
what: "w"
why: "y"
uuid: 11111111-2222-3333-4444-555555555555
schema_version: 1
---

body
"""

NO_FM_SAMPLE = "just a plain file, no frontmatter\n"


class TestStampContent(unittest.TestCase):
    def test_stamps_v0(self):
        new, status = migrate_uuid.stamp_content(V0_SAMPLE, "aaaa-bbbb-cccc")
        self.assertEqual(status, "stamped")
        self.assertIn("uuid: aaaa-bbbb-cccc", new)
        # Body untouched
        self.assertIn("The first seed.", new)
        # Original fields preserved in order
        self.assertLess(new.index("date:"), new.index("uuid:"))
        # Closing --- still present
        self.assertIn("\n---\n", new)

    def test_skips_if_uuid_present(self):
        new, status = migrate_uuid.stamp_content(V1_SAMPLE, "zzz")
        self.assertEqual(status, "has_uuid")
        self.assertEqual(new, V1_SAMPLE)

    def test_skips_if_no_frontmatter(self):
        new, status = migrate_uuid.stamp_content(NO_FM_SAMPLE, "zzz")
        self.assertEqual(status, "no_frontmatter")
        self.assertEqual(new, NO_FM_SAMPLE)

    def test_idempotent(self):
        """Run twice — second run sees the UUID and skips."""
        first, s1 = migrate_uuid.stamp_content(V0_SAMPLE, "aaaa")
        self.assertEqual(s1, "stamped")
        second, s2 = migrate_uuid.stamp_content(first, "bbbb")
        self.assertEqual(s2, "has_uuid")
        self.assertEqual(second, first)


class TestRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data_dir = Path(self.tmp) / "data"
        self.data_dir.mkdir()
        # Valid zee filename: YYYY-MM-DD-HHMM-slug.md
        (self.data_dir / "2026-04-11-1839-hello-garden-world.md").write_text(V0_SAMPLE)
        (self.data_dir / "2026-04-19-1200-with-uuid-already.md").write_text(V1_SAMPLE)
        # Non-zee filename should be ignored
        (self.data_dir / "README.md").write_text("# readme\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def test_dry_run_writes_nothing(self):
        orig = (self.data_dir / "2026-04-11-1839-hello-garden-world.md").read_text()
        result = migrate_uuid.run(self.data_dir, commit=False)
        self.assertEqual(result["stats"]["stamped"], 1)
        self.assertEqual(result["stats"]["has_uuid"], 1)
        # File unchanged on disk
        self.assertEqual(
            (self.data_dir / "2026-04-11-1839-hello-garden-world.md").read_text(),
            orig,
        )

    def test_commit_stamps_files(self):
        result = migrate_uuid.run(self.data_dir, commit=True)
        self.assertEqual(result["stats"]["stamped"], 1)
        self.assertEqual(result["stats"]["has_uuid"], 1)
        stamped = (self.data_dir / "2026-04-11-1839-hello-garden-world.md").read_text()
        self.assertTrue(UUID_RE.search(stamped))
        # V1 file still untouched
        self.assertEqual(
            (self.data_dir / "2026-04-19-1200-with-uuid-already.md").read_text(),
            V1_SAMPLE,
        )

    def test_commit_is_idempotent(self):
        migrate_uuid.run(self.data_dir, commit=True)
        # Capture UUID after first run
        first = (self.data_dir / "2026-04-11-1839-hello-garden-world.md").read_text()
        result = migrate_uuid.run(self.data_dir, commit=True)
        self.assertEqual(result["stats"]["stamped"], 0)
        self.assertEqual(result["stats"]["has_uuid"], 2)
        second = (self.data_dir / "2026-04-11-1839-hello-garden-world.md").read_text()
        self.assertEqual(first, second)

    def test_ignores_non_canonical_filenames(self):
        result = migrate_uuid.run(self.data_dir, commit=False)
        # Only two files match ZEE_FILENAME_RE; README.md ignored
        total = sum(result["stats"].values())
        self.assertEqual(total, 2)


if __name__ == "__main__":
    unittest.main()
