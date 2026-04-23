---
name: zeemap-audit
author: Zak
description: Tier 1 audit of the zeemap data dir — flags (but never modifies) zees that fail schema or parse checks. Writes a dated markdown report and appends an audit_run event to the zeemap log. Invoke daily via cron or on demand ("run audit now").
version: 0.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [zeemap, audit, schema, health]
    category: productivity
---

# Zeemap Audit — Tier 1

Read the zeemap data directory, run five checks per zee, write a report,
and relay a one-line summary to Slack. **This skill never modifies zees.**
Auto-fixes are out of scope for Tier 1; future Tier 2/3 work, designed
once Tier 1 has surfaced real-world cases, may propose mutations.

Companion to the zeemap skill. Reads the same v1 schema
(`~/.hermes/skills/productivity/zeemap/schema/v1.json`) and appends events
to the same `log.jsonl` the zeemap lifecycle tools use.

## Checks

| Check | Default severity | What it catches |
|---|---|---|
| `parse_error` | critical | YAML frontmatter doesn't load |
| `missing_required_field` | warn | Required field missing, dispatched by `schema_version` |
| `malformed_created` | warn | `created:` / `date:` value is not ISO 8601 |
| `unknown_field` | info | Frontmatter key is not in v1 schema (v1 zees only) |
| `non_canonical_filename` | info | File doesn't match `YYYY-MM-DD-HHMM-slug.md` |

Severity thresholds, ignore-list, and paths are tunable in
`data/config.json`.

### Schema dispatch

- `schema_version: 1` → strict: all v1 required fields must be present.
- `schema_version: 0` or missing → grandfathered: only `title:` plus
  *some* date hint (frontmatter `created:` / `date:` or filename prefix)
  is required. `unknown_field` is not reported for v0 zees since they
  predate the schema.

## How to run

### On demand (CLI)

```bash
python3 ~/.hermes/skills/productivity/zeemap-audit/lib/audit.py
# → writes report to data/reports/audit-YYYY-MM-DD.md
# → appends one `audit_run` event to the zeemap log
# → prints a one-line summary to stdout
```

Pass `--json` to skip report-writing and print structured output.
Pass `--no-log` to skip the log append (useful for dry runs).

### On demand (Slack)

Message the Hermes bot with something like "run zeemap audit now" —
Hermes will dispatch this skill, relay the stdout summary back to Slack,
and attach or link the report.

### Daily cron

Prepared entry for `~/.hermes/cron/jobs.json` (see
`README-CRON.md` in this dir for the exact snippet). Registering the
cron job is a separate step, gated until Tier 1 has been hand-run at
least once. The execution plan stages this as Phase 7 → Phase 8.

## What the skill emits

1. **Report** at
   `~/.hermes/skills/productivity/zeemap-audit/data/reports/audit-YYYY-MM-DD.md`
   — grouped by severity, one finding per line with filename + uuid (when
   available) + detail.
2. **Log event** appended to
   `~/.hermes/skills/productivity/zeemap/log.jsonl`:
   ```json
   {"uuid": "audit-run-<uuid>", "ts": "...", "action": "audit_run",
    "skill": "zeemap-audit", "note": "<one-line summary>"}
   ```
3. **Stdout summary** — one line like
   `zeemap audit: 28 scanned, 0 critical, 3 warn, 1 info` plus a line
   with the report path. Use this as the Slack relay when invoked from
   cron.

## Pitfalls

- **Do not mutate zees from this skill.** Tier 1 is flag-only. If a zee
  looks fixable, note it in the report and leave the fix to an explicit
  future migration.
- **Do not block on sidecar data.** The audit reads files and the schema;
  it does not need to touch the viewer, Slack, or any other service.
  If delivery to Slack fails, the report still lands on disk.
- **Respect the ignore list.** Zees whose UUID is in
  `config.ignore_uuids` are omitted from findings — useful for known
  quirks that are too expensive to fix right now.

## Roadmap (deliberately NOT in v1)

- Tier 2: propose safe auto-populations for thin-but-otherwise-valid zees
  (e.g., infer `zone:` from originating channel when missing).
- Tier 3: enrichment + decay signals (surface zees that haven't been
  touched in months; nominate candidates for grower passes).
- Feeding audit findings into the viewer (a "needs attention" lane on
  the map).
