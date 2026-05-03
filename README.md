# zeemega-skills

Master source for the Hermes skills that make an instance behave as
Zeemega. Every Hermes instance (Zak's og bot, swarm containers, future
alpha users) installs from here.

## What's shipped

| Skill | Role |
|---|---|
| [`zeemap/`](./zeemap/) | Durable-note capture. Writes zees to the instance's data dir and to Postgres when `ZEEMAP_STORE=postgres`. |
| [`zeemap-fetch/`](./zeemap-fetch/) | Read-side companion. ILIKE-ranked search across the caller's zees, returns up to 5 candidates as JSON with viewer URLs. |
| [`zeemap-audit/`](./zeemap-audit/) | Tier-1 read-only auditor. Flags (never modifies) zees that fail schema or parse checks. Companion to `zeemap`; shares the v1 schema and log. |
| [`zeemap-intro/`](./zeemap-intro/) | First-run guided experience for new users. Triggered by explicit asks ("what is zeemega?", "intro me"); walks them through one real task and plants the result as their first zee in zone `meta`. (Renamed from `zeemega-intro` in v0.4.0.) |
| [`zeemap-muse/`](./zeemap-muse/) | Character query engine. Samples the user's zee corpus via graph algorithms (random walk, type constellation, zone bridge, belief cluster, entropy slice) to surface new ideas, audio, or visuals from a personality slice. |
| [`zeemap-grow/`](./zeemap-grow/) | Grow a single zee into a leaf zee. Type-aware dispatch: belief→counter, idea→concretize, missing-metadata→enrich; otherwise expand. Leaf is linked to parent via `seeded_from`. |

## Install contract

Each skill ships as a self-contained dir under its name. To install into
a Hermes instance:

```
$HERMES_HOME/skills/productivity/zeemap/         ← contents of ./zeemap/
$HERMES_HOME/skills/productivity/zeemap-fetch/   ← contents of ./zeemap-fetch/
$HERMES_HOME/skills/productivity/zeemap-audit/   ← contents of ./zeemap-audit/
$HERMES_HOME/skills/productivity/zeemap-intro/   ← contents of ./zeemap-intro/
$HERMES_HOME/skills/productivity/zeemap-muse/    ← contents of ./zeemap-muse/
$HERMES_HOME/skills/productivity/zeemap-grow/    ← contents of ./zeemap-grow/
```

`HERMES_HOME` defaults to `~/.hermes/` for host installs and `/opt/data/`
inside the swarm container image.

Runtime state that **must not be overwritten** on upgrade:

- `zeemap/data/` — user's captured zees
- `zeemap/references/` — user's reference zees (personal profile etc.)
- `zeemap/log.jsonl` — event log
- `zeemap-audit/data/reports/` — past audit reports

Upgrade strategy: rsync the skill dir from this repo, excluding the above
paths. Packaged examples in the swarm: `hermes-swarm` Dockerfile clones
this repo at build time and copies the skills into the image under
`/opt/skills/`, with runtime dirs created empty on first boot.

## Versioning

Tags are `vMAJOR.MINOR.PATCH`. Any schema change is a minor bump; breaking
behavior change (field removed, store backend changed) is a major. Patch
is for fixes/refactors that leave the contract stable.

See [CHANGELOG.md](./CHANGELOG.md) for the running log.

## Related

- [nopslip/zeemega](https://github.com/nopslip/zeemega) — meta-repo, issue tracker, repo map, provisioning scripts.
- [nopslip/zeemap-viewer](https://github.com/nopslip/zeemap-viewer) — the app that reads zees from Postgres and renders them.
- Upstream Hermes: `nousresearch/hermes-agent`.

## Don't ship here

- User skills (e.g. `frago`, `vivero`) — those live in the user's own instance.
- Instance-specific config (`.env`, `config.yaml`) — those live in `/srv/hermes/instances/$name/data/`.
- Personal references, user profiles, captured zees.
