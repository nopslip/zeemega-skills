"""Tests for lib/write_zee.py"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import log, write_zee  # noqa: E402

FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-[a-z0-9-]+\.md$")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _run(argv, capsys_out=None):
    """Call main with argv; return (exit_code, stdout, stderr)."""
    from io import StringIO
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = StringIO(), StringIO()
    try:
        code = write_zee.main(argv)
        return code, sys.stdout.getvalue(), sys.stderr.getvalue()
    finally:
        sys.stdout, sys.stderr = old_out, old_err


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(write_zee._slugify("Hello World"), "hello-world")

    def test_word_limit(self):
        slug = write_zee._slugify("one two three four five six seven")
        self.assertEqual(slug.count("-"), 4)  # 5 words, 4 hyphens

    def test_strips_punctuation(self):
        self.assertEqual(
            write_zee._slugify("Chose X over Y — because Z!"),
            "chose-x-over-y-because"
        )

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            write_zee._slugify("!!!")


class TestYamlDq(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(write_zee._yaml_dq("hello"), '"hello"')

    def test_escapes_quote(self):
        self.assertEqual(write_zee._yaml_dq('say "hi"'), r'"say \"hi\""')

    def test_escapes_backslash(self):
        self.assertEqual(write_zee._yaml_dq("a\\b"), r'"a\\b"')

    def test_colon_space_survives(self):
        # the whole reason we quote these
        got = write_zee._yaml_dq("Note: this matters")
        self.assertEqual(got, '"Note: this matters"')


class TestFilename(unittest.TestCase):
    def test_canonical_form(self):
        name = write_zee.build_filename(
            "2026-04-19T12:34:56", "Free model roundup Apr 19"
        )
        self.assertTrue(FILENAME_RE.match(name), f"bad filename: {name}")
        self.assertTrue(name.startswith("2026-04-19-1234-"))


class TestWriteZeeEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data_dir = Path(self.tmp) / "data"
        self.data_dir.mkdir()
        self.log_path = Path(self.tmp) / "log.jsonl"
        self.body = Path(self.tmp) / "body.md"
        self.body.write_text("# Hello\n\nSome body text.\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def _argv(self, **overrides):
        args = {
            "--title": "Free model roundup",
            "--body-file": str(self.body),
            "--zone": "tools",
            "--tags": "models,research",
            "--what": "Daily snapshot: models.",
            "--why": "No-effort daily view.",
            "--type": "skill-output",
            "--skill": "free-model-discovery",
            "--skill-url": "https://example.com/skill",
            "--model": "claude-opus-4-7",
            "--data-dir": str(self.data_dir),
            "--log-path": str(self.log_path),
        }
        args.update(overrides)
        out = []
        for k, v in args.items():
            if v is None:
                continue
            out.extend([k, v])
        return out

    def test_happy_path_writes_file_and_logs(self):
        code, out, err = _run(self._argv())
        self.assertEqual(code, 0, err)
        target = Path(out.strip())
        self.assertTrue(target.exists())
        content = target.read_text()

        # Frontmatter sanity
        self.assertIn("schema_version: 1", content)
        self.assertIn('title: "Free model roundup"', content)
        self.assertIn("tags: [models, research]", content)
        self.assertIn('what: "Daily snapshot: models."', content)
        # body preserved
        self.assertIn("Some body text.", content)

        # UUID present + well-formed
        match = re.search(r"^uuid: ([0-9a-f-]+)$", content, re.MULTILINE)
        self.assertIsNotNone(match)
        zee_uuid = match.group(1)
        self.assertTrue(UUID_RE.match(zee_uuid))

        # Filename canonical
        self.assertTrue(FILENAME_RE.match(target.name))

        # Log event exists
        events = log.events_for(zee_uuid, path=self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "created")
        self.assertEqual(events[0]["actor_model"], "claude-opus-4-7")
        self.assertEqual(events[0]["skill"], "free-model-discovery")

    def test_colon_space_in_prose_survives_yaml(self):
        """Regression test for the foreign-LLM unquoted-prose bug."""
        code, out, _ = _run(self._argv(**{
            "--title": "Key finding migration gap",
            "--what": "Note: the migration is the gap, not the feature.",
            "--why": "Example: this matters because :: patterns confuse YAML.",
        }))
        self.assertEqual(code, 0)
        content = Path(out.strip()).read_text()

        # Parse with PyYAML-compatible loader to prove the YAML is valid.
        # Use a minimal hand-parser since we may not have PyYAML available:
        # just grep the values back out and confirm they are quoted.
        self.assertIn('"Note: the migration is the gap, not the feature."', content)
        self.assertIn('"Example: this matters because :: patterns confuse YAML."', content)

    def test_missing_body_file_exits_2(self):
        code, _, err = _run(self._argv(**{"--body-file": "/no/such/file"}))
        self.assertEqual(code, 2)
        self.assertIn("not found", err)

    def test_slug_collision_exits_3(self):
        # First write
        code, out, _ = _run(self._argv())
        self.assertEqual(code, 0)
        existing = Path(out.strip())

        # Freeze time by pre-creating the exact target of the second write.
        # Simpler path: write first, then immediately try again with same title —
        # but the timestamp changes by second. Instead, simulate the collision
        # by directly creating a conflicting file at the expected filename for
        # a future call, then issue that call.
        import datetime as dt
        future = dt.datetime.now().replace(microsecond=0).isoformat(timespec="seconds")
        fname = write_zee.build_filename(future, "Free model roundup")
        (self.data_dir / fname).write_text("placeholder")

        # Patch datetime.now inside write_zee to return 'future' so filename collides.
        import unittest.mock as mock
        with mock.patch("lib.write_zee.dt") as mdt:
            mdt.datetime.now.return_value = dt.datetime.fromisoformat(future)
            mdt.datetime.fromisoformat = dt.datetime.fromisoformat
            code, _, err = _run(self._argv())
        self.assertEqual(code, 3, err)
        self.assertIn("slug collision", err)

        # Cleanup so tearDown succeeds
        existing.unlink(missing_ok=True)

    def test_dry_run_writes_nothing(self):
        argv = self._argv() + ["--dry-run"]
        code, out, _ = _run(argv)
        self.assertEqual(code, 0)
        self.assertIn("--- frontmatter ---", out)
        self.assertIn("--- log event ---", out)
        # No files created
        self.assertEqual(list(self.data_dir.iterdir()), [])
        self.assertFalse(self.log_path.exists())

    def test_empty_tags_exits_2(self):
        code, _, err = _run(self._argv(**{"--tags": ""}))
        self.assertEqual(code, 2)
        self.assertIn("at least one tag", err)

    def test_seeded_from_list_renders(self):
        code, out, _ = _run(self._argv(**{
            "--seeded-from": "aaa-111,bbb-222",
        }))
        self.assertEqual(code, 0)
        content = Path(out.strip()).read_text()
        self.assertIn("seeded_from: [aaa-111, bbb-222]", content)


class TestInvocationContract(unittest.TestCase):
    """Regression tests for 2026-04-22 rogue-zee-writer bug.

    The failure was: agents shelled out `python3 write_zee.py …`. The
    terminal's `python3` was system python, which lacks `psycopg_pool`,
    so Postgres mode exploded with `ModuleNotFoundError` deep inside
    `store.py::PostgresStore._get_pool()` and fell back silently to
    local mode — zees landed on disk and never reached the DB.

    The fix was: (a) give write_zee.py a shebang pointing at a python
    with the Postgres deps available, (b) make it executable, (c)
    update SKILL.md's example to invoke it directly (no `python`
    prefix). These tests guard all three.
    """

    SCRIPT = Path(__file__).resolve().parent.parent / "lib" / "write_zee.py"
    SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"

    def test_script_has_shebang(self):
        first = self.SCRIPT.read_text().splitlines()[0]
        self.assertTrue(
            first.startswith("#!"),
            f"write_zee.py needs a shebang so agents can invoke it "
            f"directly; got first line {first!r}",
        )

    def test_shebang_python_exists_and_is_executable(self):
        first = self.SCRIPT.read_text().splitlines()[0]
        interp = first[2:].strip().split()[0]
        p = Path(interp)
        self.assertTrue(p.is_file(), f"shebang points to missing file: {interp}")
        self.assertTrue(
            os.access(p, os.X_OK),
            f"shebang interpreter is not executable: {interp}",
        )

    def test_shebang_python_can_import_psycopg_pool(self):
        """The guard for the actual bug: the interpreter write_zee.py
        runs under must have psycopg_pool available, or Postgres mode
        will fail at runtime the moment the agent writes its first zee."""
        import subprocess
        first = self.SCRIPT.read_text().splitlines()[0]
        interp = first[2:].strip().split()[0]
        result = subprocess.run(
            [interp, "-c", "import psycopg_pool"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(
            result.returncode, 0,
            f"shebang python ({interp}) cannot import psycopg_pool — "
            f"Postgres mode will fail at runtime.\nstderr: {result.stderr}",
        )

    def test_script_is_executable(self):
        self.assertTrue(
            os.access(self.SCRIPT, os.X_OK),
            "write_zee.py must be executable so agents can invoke it "
            "directly (per the SKILL.md example); run `chmod +x`",
        )

    def test_skill_md_example_does_not_prefix_with_python(self):
        """SKILL.md's canonical example is what agents copy verbatim.
        If it starts the invocation with `python `/`python3 `, the
        shebang is bypassed and we regress to the rogue-writer bug."""
        text = self.SKILL_MD.read_text()
        self.assertNotIn(
            "python ~/.hermes/skills/productivity/zeemap/lib/write_zee.py",
            text,
            "SKILL.md example must invoke write_zee.py directly, not "
            "via `python …/write_zee.py` — that bypasses the shebang.",
        )
        self.assertNotIn(
            "python3 ~/.hermes/skills/productivity/zeemap/lib/write_zee.py",
            text,
            "SKILL.md example must invoke write_zee.py directly, not "
            "via `python3 …/write_zee.py` — that bypasses the shebang.",
        )
        self.assertIn(
            "~/.hermes/skills/productivity/zeemap/lib/write_zee.py",
            text,
            "SKILL.md should still document the canonical invocation.",
        )


if __name__ == "__main__":
    unittest.main()
