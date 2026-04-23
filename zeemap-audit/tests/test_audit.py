"""Tests for zeemap-audit/lib/audit.py"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Skill lib path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import audit  # noqa: E402


SCHEMA = {
    "version": 1,
    "required": [
        "title", "zone", "tags", "what", "why",
        "created", "type", "uuid", "schema_version",
    ],
    "optional": ["model", "skill", "skill_url", "seeded_from", "updated"],
    "types": {},
    "constraints": {},
}


V1_CLEAN = """---
created: 2026-04-19T08:00:00
type: seed
zone: tools
title: "Clean v1 zee"
tags: [x]
what: "w"
why: "y"
uuid: 11111111-2222-3333-4444-555555555555
schema_version: 1
---
body
"""

V1_MISSING_WHY = """---
created: 2026-04-19T08:00:00
type: seed
zone: tools
title: "v1 missing why"
tags: [x]
what: "w"
uuid: 22222222-2222-3333-4444-555555555555
schema_version: 1
---
body
"""

V1_UNKNOWN_FIELD = """---
created: 2026-04-19T08:00:00
type: seed
zone: tools
title: "v1 with extra"
tags: [x]
what: "w"
why: "y"
uuid: 33333333-2222-3333-4444-555555555555
schema_version: 1
extra_weird_key: whatever
---
"""

V0_GRANDFATHERED_OK = """---
date: 2026-04-11
type: idea
zone: garden
title: Old school zee
tags: [old]
---
body
"""

V0_MISSING_TITLE = """---
date: 2026-04-11
type: idea
zone: x
tags: []
---
body
"""

BAD_YAML = """---
title: broken
tags: [unclosed
---
body
"""

MALFORMED_CREATED = """---
created: not-a-timestamp
type: seed
zone: x
title: "bad date"
tags: [x]
what: "w"
why: "y"
uuid: 44444444-2222-3333-4444-555555555555
schema_version: 1
---
"""


class TestCheckZee(unittest.TestCase):
    def test_clean_v1_has_no_findings(self):
        self.assertEqual(
            audit.check_zee("2026-04-19-0800-clean-v1.md", V1_CLEAN, SCHEMA),
            [],
        )

    def test_v1_missing_required_field(self):
        findings = audit.check_zee(
            "2026-04-19-0800-v1-missing-why.md", V1_MISSING_WHY, SCHEMA,
        )
        checks = [f["check"] for f in findings]
        self.assertIn("missing_required_field", checks)
        detail = next(f["detail"] for f in findings
                      if f["check"] == "missing_required_field")
        self.assertIn("why", detail)

    def test_v1_unknown_field(self):
        findings = audit.check_zee(
            "2026-04-19-0800-v1-extra.md", V1_UNKNOWN_FIELD, SCHEMA,
        )
        checks = [f["check"] for f in findings]
        self.assertIn("unknown_field", checks)

    def test_v0_grandfathered_passes(self):
        # A v0 zee with title + date should have no findings.
        findings = audit.check_zee(
            "2026-04-11-0900-old-school.md", V0_GRANDFATHERED_OK, SCHEMA,
        )
        self.assertEqual(findings, [], f"unexpected: {findings}")

    def test_v0_unknown_field_is_suppressed(self):
        # v0 predates the schema — extra fields shouldn't flag.
        v0_extra = V0_GRANDFATHERED_OK.replace(
            "tags: [old]", "tags: [old]\nsource: obsidian\nbackfilled: true"
        )
        findings = audit.check_zee(
            "2026-04-11-0900-old-school.md", v0_extra, SCHEMA,
        )
        self.assertEqual(
            [f["check"] for f in findings if f["check"] == "unknown_field"],
            [],
        )

    def test_v0_missing_title_is_warned(self):
        findings = audit.check_zee(
            "2026-04-11-0900-untitled.md", V0_MISSING_TITLE, SCHEMA,
        )
        self.assertIn(
            "missing_required_field", [f["check"] for f in findings],
        )

    def test_parse_error_reported_and_skips_field_checks(self):
        findings = audit.check_zee(
            "2026-04-19-0012-bad-yaml.md", BAD_YAML, SCHEMA,
        )
        checks = [f["check"] for f in findings]
        self.assertEqual(checks, ["parse_error"])

    def test_malformed_created_flagged(self):
        findings = audit.check_zee(
            "2026-04-19-0800-malformed.md", MALFORMED_CREATED, SCHEMA,
        )
        checks = [f["check"] for f in findings]
        self.assertIn("malformed_created", checks)

    def test_non_canonical_filename_flagged(self):
        findings = audit.check_zee(
            "not-a-canonical.md", V1_CLEAN, SCHEMA,
        )
        checks = [f["check"] for f in findings]
        self.assertIn("non_canonical_filename", checks)


class TestRunAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data_dir = Path(self.tmp) / "data"
        self.data_dir.mkdir()
        self.schema_path = Path(self.tmp) / "v1.json"
        self.schema_path.write_text(json.dumps(SCHEMA))
        self.log_path = Path(self.tmp) / "log.jsonl"
        self.reports_dir = Path(self.tmp) / "reports"

        (self.data_dir / "2026-04-19-0800-clean.md").write_text(V1_CLEAN)
        (self.data_dir / "2026-04-19-0801-missing.md").write_text(V1_MISSING_WHY)
        (self.data_dir / "2026-04-19-0012-bad.md").write_text(BAD_YAML)
        (self.data_dir / "2026-04-11-0900-grand.md").write_text(V0_GRANDFATHERED_OK)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def _config(self, ignore=None):
        return {
            "schema_path": str(self.schema_path),
            "data_dir": str(self.data_dir),
            "log_path": str(self.log_path),
            "reports_dir": str(self.reports_dir),
            "deliver": "slack",
            "severity": {
                "parse_error": "critical",
                "missing_required_field": "warn",
                "malformed_created": "warn",
                "unknown_field": "info",
                "non_canonical_filename": "info",
            },
            "ignore_uuids": ignore or [],
        }

    def test_groups_by_severity(self):
        result = audit.run_audit(self._config())
        self.assertEqual(result["zees"], 4)
        self.assertEqual(len(result["by_severity"]["critical"]), 1)  # bad yaml
        self.assertEqual(len(result["by_severity"]["warn"]), 1)      # missing why
        self.assertEqual(len(result["by_severity"]["info"]), 0)

    def test_ignore_uuids(self):
        # Suppress the missing-why finding by ignoring its uuid.
        result = audit.run_audit(
            self._config(ignore=["22222222-2222-3333-4444-555555555555"]),
        )
        self.assertEqual(len(result["by_severity"]["warn"]), 0)

    def test_render_report_structure(self):
        result = audit.run_audit(self._config())
        md = audit.render_report(result, ts="2026-04-19T20:00:00")
        self.assertIn("# Zeemap audit — 2026-04-19", md)
        self.assertIn("## critical", md)
        self.assertIn("parse_error", md)
        self.assertIn("Scanned **4** zees", md)

    def test_render_summary_one_liner(self):
        result = audit.run_audit(self._config())
        line = audit.render_summary(result)
        self.assertTrue(line.startswith("zeemap audit:"))
        self.assertIn("4 scanned", line)
        self.assertIn("1 critical", line)
        self.assertIn("1 warn", line)

    def test_clean_dir_has_no_findings(self):
        # Wipe and rewrite only clean zees
        import shutil
        shutil.rmtree(self.data_dir)
        self.data_dir.mkdir()
        (self.data_dir / "2026-04-19-0800-clean.md").write_text(V1_CLEAN)
        result = audit.run_audit(self._config())
        self.assertEqual(result["findings"], [])
        md = audit.render_report(result, ts="2026-04-19T20:00:00")
        self.assertIn("No findings", md)


if __name__ == "__main__":
    unittest.main()
