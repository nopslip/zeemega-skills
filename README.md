# zeemega-skills

Master source for the Hermes skills that make an instance behave as
Zeemega. Every Hermes instance (Zak's og bot, swarm containers, future
alpha users) installs from here.

## What's shipped

| Skill | Role |
|---|---|
| [`zeemap/`](./zeemap/) | Durable-note capture. Writes zees to the instance's data dir and to Postgres when `ZEEMAP_STORE=postgres`. |
| [`zeemap-audit/`](./zeemap-audit/) | Tier-1 read-only auditor. Flags (never modifies) zees that fail schema or parse checks. Companion to `zeemap`; shares the v1 schema and log. |

## Install contract

Each skill ships as a self-contained dir under its name. To install into
a Hermes instance:

```
$HERMES_HOME/skills/productivity/zeemap/        ← contents of ./zeemap/
$HERMES_HOME/skills/productivity/zeemap-audit/  ← contents of ./zeemap-audit/
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
