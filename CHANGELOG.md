# Changelog

## v0.1.0 — 2026-04-23

Initial extraction from Zak's local Hermes install
(`~/.hermes/skills/productivity/`). Both skills as-shipped and working in
production against og + kids instances as of this date.

- `zeemap/` — durable-note capture, v1 schema, Postgres + markdown dual store.
- `zeemap-audit/` — Tier-1 auditor, reads v1 schema, appends audit_run events to the zeemap log.
- Empty scaffold dirs for `zeemap/data/`, `zeemap/references/`, `zeemap-audit/data/reports/` (runtime, per-instance).
