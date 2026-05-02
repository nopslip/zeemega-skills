---
name: zeemap-grow
author: Zak
description: Grow a single zee into a leaf zee that builds on it — counter, concretize, expand, or enrich missing metadata, dispatched by parent state. Use when the user says "grow this zee", "develop this", "what's next from <zee>", or "evolve <id>". The leaf is a NEW zee linked to the parent via seeded_from; the parent is never modified.
version: 0.1.0
platforms: [linux]
required_environment_variables: [ZEEMAP_STORE, DATABASE_URL, CLERK_USER_ID]
metadata:
  hermes:
    tags: [zeemap, grow, leaf, seeded-from, gardening, derivative]
    category: productivity
---

# Zeemap-grow — grow a leaf from a seed

Take one zee by id or slug, dispatch to a mode based on parent state
(`enrich` if metadata is thin; otherwise type-aware: belief→counter,
idea→concretize, etc.; otherwise `expand`), render a prompt with the
parent injected, and emit JSON for the calling agent. The agent feeds
the prompt to the LLM, takes the response as the leaf body, and shells
out to `zeemap/lib/write_zee.py` with `--seeded-from <parent-uuid>` to
persist the leaf.

The parent is **never modified.** The leaf is a new zee in the same
zone, with `seeded_from` pointing at the parent. View ancestry by
traversing `seeded_from` in the viewer.

## When to use this skill

Trigger phrases:
- "grow this zee" / "grow <id>" / "grow the zee about X"
- "develop this further" / "what's the next thought from this"
- "evolve this zee"
- "expand on <zee-id>"

When NOT:
- The user wants a synthesis across many zees → use `zeemap-muse`.
- The user wants to find a zee → use `zeemap-fetch`.
- The user wants to write a brand-new zee → use `zeemap` (the writer).

## Dispatch table (living)

| Parent state | Mode | Leaf is | Leaf `type` |
|---|---|---|---|
| `what` or `why` empty / "unclear" | `enrich` | Same insight, complete metadata | same as parent |
| Parent type = `belief` | `counter` | Steel-manned opposing view | `note` |
| Parent type = `idea` | `concretize` | Concrete v1 proposal | `idea` |
| Parent type = `question` | `expand` (v0.1) | Develop the next thought | same as parent |
| Parent type = `decision` | `expand` (v0.1) | Develop the next thought | same as parent |
| Parent type = `research` | `expand` (v0.1) | Develop the next thought | same as parent |
| Anything else | `expand` | Develop the next thought | same as parent |

`enrich` wins over type-based dispatch when the parent has metadata
gaps. v0.1 ships 4 of the 7 modes (enrich, concretize, counter, expand);
the other types fall back to expand until tuned post-demo.

The mapping lives in `dispatch.yaml`. Adding a future mode = drop a
prompt template in `prompts/<mode>.md` and add a row to `dispatch.yaml`.
No Python edits required.

## CLI

```
~/.hermes/skills/productivity/zeemap-grow/lib/grow.py <zee-id-or-slug>
```

Optional flags:
- `--mode <name>` — override the dispatcher (must match a key in `dispatch.yaml` modes section).
- `--json` — emit JSON only (default is JSON; flag exists for symmetry with muse).

The script prints JSON shaped like:

```json
{
  "mode": "counter",
  "reason": "parent type=belief; metadata complete",
  "parent": { "uuid": "...", "title": "...", "type": "belief", "zone": "philosophy", "tags": [...], "what": "...", "why": "..." },
  "prompt": "<full prompt with parent injected>",
  "suggested_write": {
    "type": "note",
    "zone": "philosophy",
    "skill": "zeemap-grow",
    "seeded_from": "<parent-uuid>"
  }
}
```

## Agent runbook (what to do with the JSON)

1. Run `grow.py <id>`; parse JSON.
2. Feed `prompt` to the LLM (you, the agent).
3. The LLM response IS the leaf body.
4. Generate a leaf title from the response (first H1 line, or summarize
   to ≤8 words).
5. Generate `what` and `why` one-liners from the response (or, in
   `enrich` mode, take them directly from the response, which the
   prompt instructs the LLM to surface).
6. Shell out to `~/.hermes/skills/productivity/zeemap/lib/write_zee.py`
   with `--type`, `--zone`, `--seeded-from`, `--skill` from
   `suggested_write`, plus `--title`, `--what`, `--why` from your
   synthesis.
7. Print the resulting viewer URL (`https://app.zeemega.com/#/z/<id>`)
   to the user with one sentence: "Grew a new zee in <mode> mode from
   <parent-title> — <viewer-url>".

## Pitfalls

- **Don't read parent zee from the filesystem.** In hosted mode
  (the user's actual config) the `data/` dir is stale. The script
  uses `zeemap.lib.store.ZeeStore.get(uuid, user_id=...)` which
  handles both modes.
- **Don't mutate the parent.** The parent is read-only; the leaf is
  always a new zee.
- **Don't drop `--seeded-from`.** Without it, the link to the parent
  is lost and ancestry queries fall apart.
- **Don't generate a leaf that's a paraphrase.** If the leaf could
  apply to any parent, the prompt failed — re-run, or tune the prompt
  template.

## Future directions

- `zeemap-gardener` (cron) — picks a random zee at jittered intervals
  (6-48h) and invokes `zeemap-grow` automatically. The "Growers"
  concept from the public README.
- Tuned prompts for `revisit` (decisions), `next-thread` (research),
  `answer-candidates` (questions). Currently fall back to `expand`.
- `--through "<lens>"` — optional lens hint ("what would Brian Eno do
  with this?").
- Audit→grow queue — `zeemap-audit` writes a queue of UUIDs needing
  enrichment; `zeemap-gardener` pops from it.
- `--count N` — multiple leaves per call.
