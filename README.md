# zeemega-skills

The skill pack that makes a [Hermes](https://github.com/nousresearch/hermes-agent)
instance behave as **zeemega**: a personal agent swarm built around your
attention.

- **Landing**: [zeemega.com](https://zeemega.com)
- **App**: [app.zeemega.com](https://app.zeemega.com) — sign up, get a private
  swarm provisioned in our cloud
- **Built on**: [Hermes](https://github.com/nousresearch/hermes-agent), the
  open-source agent framework by [Nous Research](https://nousresearch.com)

## What zeemega is

You chat with your swarm the way you'd chat with any AI. What changes is what
sits behind the chat: an agent that can remember you, research while you sleep,
catch the spark of an idea as you have it, and notice when today's question
echoes something you said three weeks ago.

Conversations leave artifacts. We call them **zees** — small markdown files
(title, frontmatter, body) that capture a moment where attention caught fire.
A research synthesis. A belief stated out loud. An idea worth revisiting. The
form follows the work — a zee can carry an image, an audio clip, a generated
visual, a long-form research piece.

This is the **centaur model**: the work that's neither just human, nor just
AI. Your curiosity sets the direction. The swarm extends your reach into
research, capture, recall, and synthesis. Every zee you plant becomes context
the next conversation can lean on. The chat ends. The seed lives on.

## What's in this repo

This is the master source for the six skills that ship with zeemega. Every
Hermes instance running as a zeemega — Zak's og bot, the swarm's containers,
alpha-user instances — installs from here.

| Skill | Role |
|---|---|
| [`zeemap/`](./zeemap/) | **Capture.** Plant a zee. Writes to disk and to Postgres when `ZEEMAP_STORE=postgres`. The seed of everything else. |
| [`zeemap-grow/`](./zeemap-grow/) | **Grow.** Take an existing zee and extend it. Type-aware: belief→counter, idea→concretize, missing-metadata→enrich. The leaf links to the parent via `seeded_from`. |
| [`zeemap-muse/`](./zeemap-muse/) | **Muse.** Read across your zees and surface what your past self might suggest your present self look at next. Random walk, type constellation, zone bridge, belief cluster, entropy slice. |
| [`zeemap-fetch/`](./zeemap-fetch/) | Read-side companion. ILIKE-ranked search over the caller's zees, returns up to 5 candidates as JSON with viewer URLs. |
| [`zeemap-audit/`](./zeemap-audit/) | Tier-1 read-only auditor. Flags (never modifies) zees that fail schema or parse checks. |
| [`zeemap-intro/`](./zeemap-intro/) | First-run guided experience. Walks a new user through one real task and plants the result as their first zee. |

`capture`, `grow`, and `muse` are the originality. `fetch`, `audit`, and
`intro` are the tooling that keeps the pack healthy.

## Install contract

Each skill ships as a self-contained dir under its name. To install into a
Hermes instance:

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

- `zeemap/data/` — captured zees
- `zeemap/references/` — reference zees (personal profile etc.)
- `zeemap/log.jsonl` — event log
- `zeemap-audit/data/reports/` — past audit reports

Upgrade strategy: rsync the skill dir from this repo, excluding the above
paths. The swarm's Dockerfile clones this repo at build time and copies the
skills into the image under `/opt/skills/`, with runtime dirs created empty
on first boot.

## Versioning

Tags are `vMAJOR.MINOR.PATCH`. Schema change → minor bump. Breaking behavior
change (field removed, store backend changed) → major. Patch is for
fixes/refactors that leave the contract stable.

See [CHANGELOG.md](./CHANGELOG.md) for the running log.

## Try it

Easiest path: [sign up at app.zeemega.com](https://app.zeemega.com). We
provision each swarm by hand — pre-wired with these skills, a viewer for
browsing what you produce, and a Telegram bot you can DM. No setup on your
side. Private beta, short wait.

If you'd rather run your own Hermes instance and install the pack manually,
follow the install contract above. Issues and PRs welcome.

## Related

- [nopslip/zeemega](https://github.com/nopslip/zeemega) — meta-repo, repo map,
  provisioning scripts.
- [nopslip/zeemap-viewer](https://github.com/nopslip/zeemap-viewer) — the app
  that reads zees from Postgres and renders them.
- [nopslip/zeemaps-landing](https://github.com/nopslip/zeemaps-landing) —
  zeemega.com landing site and docs.
- Upstream Hermes: [`nousresearch/hermes-agent`](https://github.com/nousresearch/hermes-agent).

## Don't ship here

- User skills (e.g. `frago`, `vivero`) — those live in the user's own instance.
- Instance-specific config (`.env`, `config.yaml`) — those live in
  `/srv/hermes/instances/$name/data/`.
- Personal references, user profiles, captured zees.
