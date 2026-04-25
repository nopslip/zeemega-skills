# Changelog

## v0.1.1 — 2026-04-25

Hardening release. No schema or behavior change for callers that do
the right thing; two new guards that refuse silent data loss when
they don't.

- `zeemap/lib/write_zee.py` (#1 follow-up): defense against the
  silent local-fallback pattern. New exit code `6`.
  - If `ZEEMAP_STORE=postgres` and `psycopg_pool` isn't importable in
    the current interpreter, the script now re-execs itself under a
    discovered hermes venv python (checks `$VIRTUAL_ENV`,
    `$HERMES_HOME/hermes-agent/venv`, `/opt/hermes/.venv`,
    `~/.hermes/hermes-agent/venv`). Fixes canonical writes that were
    bypassing PG because the agent invoked the script as `python3 …`
    (system python, no `psycopg_pool`) instead of executing it via
    shebang.
  - If `DATABASE_URL` is set in env but the caller passed
    `ZEEMAP_STORE=local`, the script refuses with exit `6`. Catches
    the "agent treats Postgres error as a workaround target and
    forces local mode" pattern that produced orphan `.md` files
    invisible to the viewer.
- `zeemap/SKILL.md`: documents exit `6` and explicitly tells the
  agent never to retry with `ZEEMAP_STORE=local` as a workaround.
- `zeemap/lib/store.py` (#3): dropped a docstring reference to
  `/home/dev/hermes/zee-storage-migration-plan.md` — Zak-local path
  that didn't resolve for anyone else.

Closes nopslip/zeemega-skills#2 (kept the venv-specific shebang —
shim in the kids image makes it portable today, and the re-exec
guard handles the agent-bypasses-shebang failure mode that was the
real regression risk). Closes #3.

## v0.1.0 — 2026-04-23

Initial extraction from Zak's local Hermes install
(`~/.hermes/skills/productivity/`). Both skills as-shipped and working in
production against og + kids instances as of this date.

- `zeemap/` — durable-note capture, v1 schema, Postgres + markdown dual store.
- `zeemap-audit/` — Tier-1 auditor, reads v1 schema, appends audit_run events to the zeemap log.
- Empty scaffold dirs for `zeemap/data/`, `zeemap/references/`, `zeemap-audit/data/reports/` (runtime, per-instance).
