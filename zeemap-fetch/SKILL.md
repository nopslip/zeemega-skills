---
name: zeemap-fetch
author: Zak
description: Find existing zees in the user's zeemap by free-text query and return up to 5 ranked candidates (title, zone, visibility, shareable URL). Use when the user asks for an existing zee — phrases like "link me on…", "find my zee about…", "send me the link to…", "what was that note on…". This skill READS only; it does not create, edit, or change visibility on zees.
version: 0.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [knowledge-retrieval, search, personal]
    category: productivity
---

# Zeemap-fetch — find existing zees

This skill is the read counterpart to `zeemap`. Given a query, it
returns up to 5 ranked candidate zees as JSON. The agent reads the
JSON and replies conversationally with the user.

## When to use this skill

Trigger phrases:
- "link me on my zee about X"
- "find my zee about X"
- "send me the link to my X note"
- "what was that note on X"
- "search my zees for X"

If the user asks to *write* or *create*, that's the `zeemap` skill.
If the user asks to *change visibility* on a zee, do NOT use this
skill — direct them to the viewer (visibility changes are user-driven
only, by design).

## Output shape

```json
{
  "query": "la garita",
  "matches": [
    {
      "uuid": "...",
      "filename": "2026-04-22-0900-la-garita-property-notes",
      "title": "La Garita property notes",
      "zone": "travel",
      "type": "note",
      "tags": ["travel", "real-estate"],
      "created": "2026-04-22T09:00:00",
      "visibility": "private",
      "what": "Notes from the La Garita lot walk-through.",
      "snippet": "First impressions of the lot...",
      "in_app_url": "https://app.zeemega.com/#/z/2026-04-22-0900-la-garita-property-notes",
      "public_url": null
    }
  ]
}
```

- `matches` is up to 5 entries, ranked by match quality.
- `public_url` is set only when `visibility IN ('unlisted', 'public')`.
- `snippet` is ~120 chars from the body to help disambiguate.

If no matches: `{ "query": "...", "matches": [] }`.

## How to talk to the user with the result

After running the CLI, summarize results like:

> Found 3 zees for "la garita":
> 1. **La Garita property notes** (private, travel) — your link: <in_app_url>
> 2. **La Garita lot photos** (link-only, travel) — share link: <public_url>
> 3. ...
>
> Want me to remind you what's in any of them?

If exactly one strong match (rank 0 or 1) **and** the user asked for "the link", paste it inline without listing alternatives.

**Never auto-promote a private zee to shareable.** If the user asks
to share a private zee, point them to the viewer chip — the design
deliberately keeps visibility flips out of agent control.

## Invocation

```bash
~/.hermes/skills/productivity/zeemap-fetch/lib/find_zees.py "la garita"
```

The script reads:
- `DATABASE_URL` — required for connecting to Postgres
- `CLERK_USER_ID` (or future `HERMES_OWNER_ID`) — required for owner scope
- `ZEEMEGA_VIEWER_URL` — optional, defaults to `https://app.zeemega.com`

## Exit codes

- `0` success; JSON written to stdout
- `2` bad CLI input (missing query)
- `5` `CLERK_USER_ID` env not set
- `6` `psycopg_pool` unavailable in current interpreter (mirrors `write_zee.py`)

## Pitfalls

- **Don't summarize zee bodies the user hasn't asked to read.** This
  skill returns excerpts only; the body lives behind the URL.
- **Don't shorten URLs.** Pass them through verbatim so they remain
  copy-pasteable.
- **Don't run this for new-zee writes** — that's the `zeemap` skill.
