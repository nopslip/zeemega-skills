# Changelog

## v0.4.1 — 2026-05-03

Hardening release. Decouple instance identity from Clerk by introducing
`HERMES_OWNER_ID` (the internal `users.id` UUID) as the preferred env
var, with `CLERK_USER_ID` retained as a deprecated fallback. Closes
nopslip/zeemega-skills#4.

- **`zeemap/lib/write_zee.py`**: prefer `HERMES_OWNER_ID`; pass it
  through directly as `user_id` (no `resolve_user` round-trip per
  write). Falls back to `CLERK_USER_ID` + `resolve_user` with a stderr
  deprecation warning. Adds boundary validation: `HERMES_OWNER_ID` must
  parse as a UUID; `CLERK_USER_ID` must NOT — catches the two operator
  foot-guns where the values get pasted into the wrong var.
- **`zeemap-grow/lib/reader.py`**: same precedence + validation rules.
- **`zeemap-fetch/lib/find_zees.py`**: was already accepting either env
  var name but treated both values as Clerk subjects (would `SELECT id
  FROM users WHERE clerk_id = <uuid>` and fail). Now skips `_resolve_user_id`
  when `HERMES_OWNER_ID` is set. Adds the same boundary validation.
- **`zeemap/lib/store.py`** docstring: documents the preferred path
  (caller already has the UUID) vs. legacy resolve_user fallback.
- **SKILL.md updates**: `zeemap`, `zeemap-intro`, `zeemap-grow`,
  `zeemap-fetch` now document `HERMES_OWNER_ID` as the required env var.
- **Tests**: 6 new boundary-validation cases in `zeemap/tests/test_write_zee.py`
  (covers exit-5 paths + a mock-store hot-path test that proves
  `resolve_user` is not called when `HERMES_OWNER_ID` is set).
  5 new cases in new `zeemap-grow/tests/test_reader.py`. 3 new
  CLI-level cases in `zeemap-fetch/tests/test_find_zees.py`.

Migration for existing instances (one-shot, post-release):

```sql
SELECT id FROM users WHERE clerk_id = '<current CLERK_USER_ID value>';
```

Append `HERMES_OWNER_ID=<that-uuid>` to the instance's `.env` and
restart. `CLERK_USER_ID` can stay alongside during the transition;
remove in a follow-up. The `provision/new-instance.sh` script in
`nopslip/zeemega` is being updated in the same window to write
`HERMES_OWNER_ID` directly for new instances.

The `CLERK_USER_ID` fallback path will be removed in a future major
release. New issue to track that follow-up will be filed.

## v0.4.0 — 2026-05-02

Naming convention: every skill now uses the `zeemap-*` prefix; `zeemega`
is reserved for the brand. Two new skills land; one is renamed.

- **Renamed:** `zeemega-intro/` → `zeemap-intro/`. Skill behavior is
  unchanged. Install contract changes from
  `$HERMES_HOME/skills/productivity/zeemega-intro/` to
  `$HERMES_HOME/skills/productivity/zeemap-intro/`. Anyone with the old
  path baked into install scripts must update; the v0.4.0 sync step in
  the release runbook moves the old user-local dir aside (renames to
  `zeemega-intro.old.<date>`) so a missed reference fails loudly rather
  than silently shadowing the new install.
- **New:** `zeemap-muse/` — character query engine. Samples the user's
  zee corpus via six graph algorithms (random walk, type constellation,
  zone bridge, belief cluster, entropy slice, hybrid) to extract a
  personality slice and surface new ideas, audio narration, or visual
  fingerprints. Follows the established skill-as-tool pattern: emits a
  synthesis prompt for the calling agent to feed to the LLM. Same code
  as the prior `~/.hermes/skills/research/zeemega/` skill, repackaged
  under the v0.4.0 naming convention.
- **New:** `zeemap-grow/` — grow one zee into a leaf zee that builds on
  it. Type-aware dispatch (`enrich` if metadata is thin; otherwise
  `belief→counter`, `idea→concretize`; otherwise `expand`) selects a
  prompt template; the calling agent feeds the rendered prompt to the
  LLM, then shells out to `zeemap/lib/write_zee.py` with
  `--seeded-from <parent-uuid>` to persist the leaf. v0.1 ships 4 of 7
  planned modes; the rest fall back to `expand` until tuned. Adding a
  future mode = drop a prompt template + add a row to `dispatch.yaml`.
- **Repo flips PUBLIC** with this release. Prior versions were private;
  the open-source surface starts at v0.4.0.

## v0.3.0 — 2026-04-28

New skill plus a private-link bug fix in `zeemap`.

- `zeemega-intro/` — first-run guided experience for new Zeemega users.
  Triggered only by explicit asks ("what is zeemega?", "intro me", "give
  me the tour") — deliberately not by bare greetings. Walks the user
  through one real research/decision/plan task using whatever tools fit
  (web_search, structured analysis), then plants the result as their
  first zee in zone `meta` with tags `intro,first-zee`. The whole skill
  is the demo: people don't yet know what an agent does, and one rich
  multi-step result around a topic they actually care about teaches
  what words can't. No new scripts; reuses `zeemap/lib/write_zee.py`
  for the canonical write so the meta zee lands in Postgres like any
  other.
- `zeemap/SKILL.md` — fixed the private-zee viewer link. The old
  guidance produced `https://app.zeemega.com/z/<filename>.md` which
  404s through to the SPA shell. New guidance produces
  `https://app.zeemega.com/#/z/<id>` (hash route, no `.md`), matching
  the viewer's `route.ts` source of truth (`HASH_PREFIX = '#/z/'`,
  `zeeIdFor` strips `.md`). Public `/p/<id>` guidance unchanged. Found
  after a user got a malformed link in chat.

## v0.2.0 — 2026-04-25

New skill: read-side companion to `zeemap`.

- `zeemap-fetch/` — `find_zees.py` CLI runs an ILIKE-ranked search
  across title/zone/tags/body for the caller's `CLERK_USER_ID` (or
  `HERMES_OWNER_ID`) and emits up to 5 candidates as JSON to stdout.
  Returns `in_app_url` always, `public_url` only when the zee's
  `visibility ∈ {unlisted, public}`. Mirrors `write_zee.py`'s exit-6
  hermes-venv re-exec guard so silent fallback isn't possible.
- Trigger phrases live in `zeemap-fetch/SKILL.md`. The skill explicitly
  forbids auto-promoting visibility — visibility flips are user-driven
  only, by design.
- 7 unit tests + 1 opt-in integration test (skipped without
  `DATABASE_URL` + `CLERK_USER_ID`).

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
