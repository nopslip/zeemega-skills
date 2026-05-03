---
name: zeemap
author: Zak
description: Capture durable seeds (decisions, ideas, research, beliefs, questions) from conversations into ~/.hermes/skills/productivity/zeemap/data/ as timestamped markdown files with frontmatter. Each seed is tagged with a free-form zone for later organization on the map.
version: 0.4.1
platforms: [linux]
metadata:
  hermes:
    tags: [knowledge-capture, notes, personal, markdown, zones]
    category: productivity
---

# Zeemap — durable seed capture

Zeemap is a directory (`~/.hermes/skills/productivity/zeemap/data/`) that
accumulates long-lived **seeds** (notes) from conversations. Unlike session
logs or short-term memory, zeemap files are meant to be readable in a month
or a year and to survive across sessions, updates, and context resets.

The bigger picture:
- **MAP** = the knowledge territory (all zones combined)
- **ZONES** = free-form labels grouping related seeds (often, though not
  always, ≈ Slack channels)
- **SEEDS** = individual notes planted in conversations

Seeds grow. You are writing a first draft, not a final word. Future
"gardening" skills will re-read zees, enrich thin fields, connect
neighbors — your job at capture is to be honest and faithful, not
polished.

## When to use this skill

Write a seed when the conversation produces any of these:

- **A decision with rationale.** "We picked X over Y because Z." Future-you
  will want the *why*, not just the outcome.
- **An idea worth revisiting.** Something speculative or unfinished that
  shouldn't be forgotten just because the current thread ended.
- **A research finding or distilled conclusion.** After gathering
  information, write down what was learned in plain language.
- **A belief or principle the user states.** If the user says something
  like "I think the best way to X is Y because..." — that's a belief
  worth recording verbatim.
- **An open question.** Something that couldn't be resolved now but is
  worth holding onto. These are often the seeds of future work.
- **An explicit save request.** If the user says "save this", "remember
  this", "plant this", "add this to my notes", or similar — always write
  a seed, even if you'd otherwise judge the content routine.

## When NOT to use this skill

- Greetings, small talk, or meta-chatter about yourself
- Every reply that felt useful — the bar is "worth re-reading in a month",
  not "was helpful just now"
- Code execution output, tool results, or debug traces — those belong in
  logs, not zeemap
- Things the user is actively working on in a scratch file — zeemap is for
  the distilled conclusion, not the work-in-progress

If you're unsure whether something is seed-worthy, prefer not writing.
It's easier to add a seed later than to prune clutter.

## Frontmatter schema

```yaml
---
# Required
created: 2026-04-18T14:31:00        # ISO timestamp, capture time
type: seed | note | decision | research | belief | question | idea
zone: <free-form lowercase string>
title: Short human-readable title
tags: [tag1, tag2]
what: One-line description of the zee
why: One-line "why does this matter"

# Optional
updated: 2026-04-19T09:00:00        # only if edited after creation
model: claude-opus-4-7              # LLM used to most recently save this zee
source: obsidian | conversation | web-research | ...
source_run_id: <id from originating skill/cron run>
backfilled: true
original_date: 2026-04-10           # when the research actually happened
---
```

### Required fields

- **created**: ISO 8601 timestamp of capture (`date +%Y-%m-%dT%H:%M:%S`).
  Replaces the older day-only `date:` field. For backfilled notes, this
  is still the *capture/import* time — use `original_date` for when the
  work actually happened.
- **type**: one of the seven values above. When genuinely ambiguous, use
  `seed`.
- **zone**: a short lowercase label grouping related seeds. Free-form, not
  enumerated. Common examples: `health`, `tech`, `social`, `travel`,
  `kids-discovery`, `family`, `work`, `philosophy`. Use `uncategorized`
  when you genuinely can't tell. Pick a zone that already exists in
  `data/` if one fits —
  `ls data/ | xargs grep -h '^zone:' | sort -u` shows the current
  vocabulary. Don't create a new zone for every seed; reuse builds the
  map.
- **title**: a short human sentence, not a filename. Capitalize normally.
- **tags**: 2–6 short lowercase tags. Always include `backfill` in tags
  for backfilled notes. Useful for future grep.
- **what**: one line describing the zee. See the discretion section below
  when this isn't obvious.
- **why**: one line on why it matters. See the discretion section below
  when this isn't obvious.

### Optional fields

- **updated**: ISO timestamp. Set *only* when you edit an existing zee.
  Absent on fresh seeds.
- **model**: the LLM model ID that most recently saved this zee (e.g.
  `claude-opus-4-7`, `gpt-5`, `claude-sonnet-4-6`). Not an author — the
  author is the user. Include yours if you know it; omit if unknown.
  Gardening agents update this on enrichment.
- **source**: where the content came from (`obsidian`, `notes`,
  `conversation`, `web-research`, etc.). Useful provenance.
- **source_run_id**: id of the originating skill or cron run, when
  applicable.
- **backfilled**: `true` for imported historical notes. Omit on live
  captures.
- **original_date**: when the research actually happened. Only with
  `backfilled: true`.

## When `what` and `why` aren't obvious

`what` and `why` are required fields, but in practice they're often
unclear at capture time. An idea arrives before it can be fully
articulated; a belief is stated without its roots explained. Forcing a
confident-sounding answer in those moments is worse than being honest
about the uncertainty — the hallucinated reason survives, gets trusted,
and rots the map.

**The rule: write what you can honestly see. Don't invent meaning that
isn't there.**

Three cases:

1. **Both clear.** Write them normally.
   `what: Chose systemd user service over system service.`
   `why: No sudo needed; survives user logout via loginctl linger.`

2. **`what` clear, `why` not.** Write `what` normally; capture `why` as
   the honest state.
   `what: User keeps returning to the gardening metaphor for zeemap.`
   `why: unclear — mentioned three times this week, driver not yet named.`

3. **Both murky.** Capture what you *do* see — the shape of the thought,
   the words used, the context. Put the rich prose in the body.
   `what: A felt sense that zeemap should feel like a garden, not a database.`
   `why: not yet articulated — see body.`

**Flag uncertainty in the value itself** so gardening passes can find
and enrich it. Searchable markers:
- `unclear —` followed by context
- `not yet articulated`
- `tentative:` prefix
- `see body` when the body holds context the one-liner can't

Avoid bare `tbd` or empty-looking placeholders — they strip the context
a gardener would use to decide how to enrich.

**Why this split matters.** Your job at capture is the honest first
draft, not the polished version. A `why:` that says "I don't know yet"
is a seed a gardener can grow. A `why:` that confidently invents a
reason is a weed that looks like a flower.

### How to choose a zone

Today, zone selection is your judgment based on the conversation's
subject matter. In a future phase, a gateway hook may pre-set the zone
from the originating Slack channel name; until then, infer it from
content. A few heuristics:

- Conversations about sleep, nutrition, exercise, mental state → `health`
- Conversations about code, infrastructure, tools, debugging → `tech`
- Conversations about people, relationships, conversations → `social`
- Conversations about trips, places, logistics → `travel`
- Conversations about parenting, kids' learning, family activities →
  `kids-discovery` or `family`
- Genuinely cross-cutting or unclear → `uncategorized`

The user can always retag later. Don't ask permission for the zone
unless the conversation could plausibly belong to two very different
ones.

## Filename convention

`~/.hermes/skills/productivity/zeemap/data/YYYY-MM-DD-HHMM-<slug>.md`

- Prefix with `date +%Y-%m-%d-%H%M` so files sort chronologically with
  `ls -lt`. This is derived from `created:` — the date-and-minute part
  of the ISO timestamp.
- `<slug>` is lowercase, hyphen-separated, derived from the title,
  2–5 words max.
- If two files collide within the same minute, append `-2`, `-3`, etc.
- Do **not** prefix the filename with the zone — zone lives in
  frontmatter to keep the directory flat.

## Grandfathered zees

Seeds written before v0.4.0 of this skill used `date:` (day-only)
instead of `created:`, and had no `what:` or `why:` fields. These are
valid — the viewer and gardening tooling read them as-is. Don't rewrite
them silently; a dedicated migration or gardening pass can enrich them
over time.

## Backfill workflow

Importing past research (notes from before Zeemap existed, Obsidian
dumps, old research files) into the map. The user pastes or describes
old research in chat; the agent formats it as a seed.

### When to backfill
- User says "backfill this", "add this old note", "import this"
- User pastes research that clearly predates the current conversation
- User describes work done before Zeemap existed

### How to backfill
1. Identify the **original date** of the research (ask the user if
   unclear, or infer from context like "a few days ago", "last month").
2. Write the seed with today's ISO timestamp as `created:` (capture
   time) in filename prefix and frontmatter.
3. Add `backfilled: true`, `original_date`, and `source` to frontmatter.
4. Include `backfill` in the tags list.
5. Format the pasted content into clean markdown — don't just dump raw
   text. Distill where possible, but preserve the original insights
   faithfully.
6. If the user pastes multiple old notes at once, write one seed per
   distinct topic (same as live captures).

### Key distinction
- `created` = when the seed was *planted* (capture time, today)
- `original_date` = when the *research actually happened*
- Filename sorts by capture time, so backfills show up "now" in `ls -lt`
- `original_date` preserves temporal truth for future queries

### Filtering
```bash
# Live captures only (no backfills)
grep -L 'backfilled: true' ~/.hermes/skills/productivity/zeemap/data/*.md

# Backfills only
grep -l 'backfilled: true' ~/.hermes/skills/productivity/zeemap/data/*.md

# Backfills from Obsidian
grep -l 'source: obsidian' ~/.hermes/skills/productivity/zeemap/data/*.md

# Zees needing gardening (thin or uncertain what/why)
grep -lE '^(what|why): (unclear|not yet articulated|tentative|tbd)' \
  ~/.hermes/skills/productivity/zeemap/data/*.md
```

## How to write a seed — **ALWAYS via `write_zee.py`**

**Hard rule. Never write to `data/*.md` directly.** Not with `cat > …`,
not with a `Write` tool, not with `echo`. The canonical writer is
`lib/write_zee.py`, which:

- stamps `uuid` + `schema_version` (required fields you'd otherwise
  forget);
- routes through `ZeeStore` so the zee lands wherever the environment
  says (filesystem in local mode, Postgres + `pg_notify` in hosted
  mode — **a direct `.md` write silently bypasses the database and the
  user never sees the zee in the viewer**);
- quotes `title:` / `what:` / `why:` correctly so colon-space prose
  doesn't wreck the YAML.

Hand-rolling frontmatter is the #1 way zees end up invisible or
malformed. The script exists specifically so you don't have to.

### Invocation

Body content goes in a temp file, then shell out:

```bash
BODY=$(mktemp --suffix=.md)
cat > "$BODY" << 'BODY_END'
# Why we chose X over Y

Plain-language explanation. Write the thing you'd want to read in six
months. Include the alternatives considered and why they were rejected.
Name any constraints that forced the choice.

## Open questions
- Things that weren't resolved.
- Future refinements.
BODY_END

~/.hermes/skills/productivity/zeemap/lib/write_zee.py \
  --title   "Why we chose X over Y" \
  --body-file "$BODY" \
  --zone    tech \
  --tags    "project-name,architecture" \
  --what    "Chose X over Y for <specific constraint>." \
  --why     "<constraint> ruled out Y; X also gives <additional benefit>." \
  --type    decision \
  --skill   zeemap \
  --model   claude-opus-4-7

rm "$BODY"
```

The script prints the canonical `.md` filename on success (exit 0). It
does **not** need the data directory passed — it reads `ZEEMAP_DATA_DIR`
from the environment.

### Required flags

`--title`, `--body-file`, `--zone`, `--tags`, `--what`, `--why`, `--type`.
The `type` value must be one of:
`seed | note | decision | research | belief | question | idea`.

### Optional flags

- `--skill <name>` — the originating skill (e.g. `zeemap`, `blogwatcher`,
  `fragrance-research`). **Always set this** so audit can trace zees
  back to the producer.
- `--model <id>` — the LLM that composed the zee.
- `--skill-url <url>` — link back to the skill's repo/docs.
- `--seeded-from <uuid,uuid,…>` — for zees that derive from other zees
  (seed graph).
- `--session-id <id>` — logged to the event stream.
- `--dry-run` — print frontmatter + event without writing. Use this to
  verify before a real call.

### Exit codes

`0` success · `2` bad CLI input · `3` slug collision (retry with a
slightly different title or wait a minute) · `4` zee persisted but
event log append failed · `5` postgres mode without `HERMES_OWNER_ID`
(or legacy `CLERK_USER_ID`), or one of those vars failed boundary
validation (`HERMES_OWNER_ID` must be a UUID; `CLERK_USER_ID` must not be one)
env · `6` postgres required but unavailable (psycopg_pool missing
from this interpreter and no hermes venv recoverable) OR
`DATABASE_URL` is set but `ZEEMAP_STORE=local` was chosen. See the
next section for why `6` exists.

### Exit 6 — never "fix" it by forcing `ZEEMAP_STORE=local`

If a write exits `6`, **do not retry the command with
`ZEEMAP_STORE=local`**. That flag silently bypasses the database and
the user never sees the zee in the viewer (this has happened and
caused data loss). Exit `6` means one of:

- `psycopg_pool` isn't importable in the interpreter running the
  script. Fix by executing `write_zee.py` directly (`./write_zee.py
  …`, which uses the venv shebang) or by invoking it via the hermes
  venv python explicitly (`/home/dev/.hermes/hermes-agent/venv/bin/python
  …` on the host, `/opt/hermes/.venv/bin/python …` in the kids
  container). The script also tries to re-exec itself under a
  discovered venv automatically — if it still exits `6`, no venv on
  this box has `psycopg_pool`, and that's a setup error to surface
  to the user.
- `DATABASE_URL` is set but the caller passed `ZEEMAP_STORE=local`
  as a command-line override. This guard exists specifically to
  catch an agent silent-bypassing Postgres because of a transient
  error. Surface the underlying error; do not work around this.

### Prose fields already quoted

`--title` / `--what` / `--why` arrive as shell args and the script
double-quotes them correctly in the emitted YAML. You don't need to
add your own quotes — the script handles `: `, backslashes, and
embedded quotes. Do **not** try to pre-format them as YAML.

## Pitfalls

- **Don't write too many seeds.** If in doubt, don't write. The map
  should be signal, not a chat log.
- **Don't re-capture things already captured this session.** Check with
  `ls -lt ~/.hermes/skills/productivity/zeemap/data/ | head -5` before
  writing if you think you might be duplicating.
- **Don't write seeds *about* the current task in the current task.**
  If the user is debugging a bug right now, zeemap isn't for the
  debugging transcript — it's for the distilled lesson after the bug
  is fixed.
- **Don't invent a confident `why:` when you don't have one.** Use the
  honest-uncertainty phrasings from the discretion section. A fake
  reason rots the map.
- **Use the locked frontmatter fields consistently.** The schema is
  the schema; if a piece of metadata genuinely needs a home that isn't
  there, put it in `tags` for now and propose a schema change rather
  than inventing a one-off field.
- **Don't proliferate zones.** Reuse existing zone labels when one
  fits. A new zone is a deliberate choice (typically when a new
  channel/area of life appears), not the default.
- **Don't write subdirectories.** Flat structure; zone lives in
  frontmatter.
- **Don't write outside `~/.hermes/skills/productivity/zeemap/data/`.**
- **Don't bypass `write_zee.py`.** No `cat > data/*.md`, no `Write` tool
  against the data dir, no hand-rolled YAML. If you're tempted to
  construct frontmatter yourself, stop — the script's whole purpose is
  to do that correctly (and to route into Postgres in hosted mode).

## Verification

After writing a seed, confirm the exit code was 0 and the script
printed a filename. **Don't** `cat` the file to re-read the
frontmatter — in hosted mode there's no file on disk, only a row in
Postgres. If you need to sanity-check, re-run with `--dry-run` first
on the same args and inspect the printed frontmatter + event block.

Mention in chat that you saved a seed (with its zone) so the user can
look at it in the viewer. **Always include the viewer link** — construct
it from the filename that `write_zee.py` printed, **stripping the `.md`
suffix**:

```
https://app.zeemega.com/#/z/<id>
```

Example: if the script prints
`2026-04-28-0301-the-alexander-technique-posture-awareness.md`, the link
is
`https://app.zeemega.com/#/z/2026-04-28-0301-the-alexander-technique-posture-awareness`
— no `.md`, and note the `#/z/` hash route. The viewer reads the id from
the URL fragment, not the path; a `/z/<...>` path link will 404 through
to the SPA shell.

Use `#/z/<id>` for private zees (the default). The `/p/<id>` route is
for public/unlisted zees only (real path, server-rendered, also no
`.md`) — never return that unless visibility was explicitly set to
public or unlisted.

## Failure mode to watch for

If you, the agent, find yourself thinking "this feels seed-worthy"
about a substantive conversation and you still don't write one, that's
the exact failure mode to flag. Err on the side of writing in the first
few conversations after install so the user can evaluate whether the
bar is calibrated correctly.

The other failure mode: writing a confident `what:`/`why:` because the
schema demanded one, when the honest answer was "I don't know yet."
Prefer "unclear — " to invention.
