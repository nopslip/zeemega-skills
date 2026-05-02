---
name: zeemap-muse
author: Zak
description: >
  Character query engine for Zeemega. Samples the zeemap graph via graph
  algorithms (random walk, type constellation, zone bridge, belief cluster,
  entropy slice) to build personality slices, then surfaces new ideas,
  media, and content from the slice. The first step toward a digital
  clone — not through a system prompt, but through the actual artifacts
  of thinking.
version: 0.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [ai-me, character-query, digital-clone, augmented-creativity, content-generation]
    category: productivity
---

# Zeemega — Character Query Engine

> "The garden IS the seed." — Zak, April 2026

Zeemega queries the zeemap graph to extract personality slices — random
but structured subsets of zees that, together, paint a portrait of who you
are at a moment in time. From that portrait, it surfaces new ideas, media,
and content that you wouldn't have found alone.

This is the prototype for the digital clone. Not a system prompt. Not a
memory dump. A *queryable graph of identity* that generates new things.

## When to use this skill

- "Show me a character print" / "What does my zee graph say about me"
- "Give me a random slice of my zees"
- "Surprise me from my own archive"
- "What would my clone think about X"
- "Generate something new from my zees"
- Exploring what emerges from the intersection of different parts of
  your thinking

## What it generates

From a character slice (a subset of zees), zeemega can produce:

- **Text** — synthesis, connections, new directions, the "clone's take"
- **Audio** — TTS narration of the synthesis, or sonified zee data
- **Visual** — generative art representing the character fingerprint
- **Media** — any combination of the above as a "character print" artifact

The goal is always: **surface something new**. Not summarize. Not repeat.
Find the hidden pattern, the unexpected bridge, the next exploration.

## Architecture

```
zeemap/data/*.md  -->  parser  -->  graph indexes
                                      |
                    +-----------------+-----------------+
                    |                 |                 |
              +-----+-----+   +------+------+   +-----+-----+
              | Algorithm  |   |  Algorithm  |   | Algorithm  |
              |  Selector  |   |  Selector   |   |  Selector  |
              +-----+-----+   +------+------+   +-----+-----+
                    |                |                 |
                    +----------------+-----------------+
                                     |
                              +------+------+
                              | Synthesizer |
                              |  (LLM call) |
                              +------+------+
                                     |
                    +----------------+----------------+
                    |                |                |
                  text             audio           visual
```

## Query Algorithms

### 1. Random Walk (`--mode walk`)
Start at a random zee (or a specific tag). Follow tag edges to neighbors.
Builds a tree of depth N. Surfaces chains of thought — how one idea
connects to another through your actual tag graph.

Best at: 50+ zees. At 34, chains are short.

### 2. Type Constellation (`--mode constellation`)
Pick N zees from each type (belief, idea, research, decision, seed).
Gives a balanced personality slice — the thinker, the doer, the researcher.

Best at: any scale. Works even at 10 zees.

### 3. Zone Bridge (`--mode bridge`)
Pick from two zones that don't normally connect. Find bridging tags.
Forces cross-pollination: what happens when your philosophy meets your
fragrance research?

Best at: 20+ zees with 3+ zones.

### 4. Belief Cluster (`--mode beliefs`)
Pull all beliefs and ideas — the core identity. These are the things
you'd want your clone to carry forward.

Best at: any scale.

### 5. Entropy Slice (`--mode entropy`)
Weighted random by tag rarity. Prefers the surprising over the obvious.
The zees with rare tags get pulled up — the specific, the weird, the
uniquely you.

Best at: 30+ zees. Needs tag diversity to work.

### 6. Hybrid (`--mode hybrid`, default)
Runs 2-3 algorithms and merges the results. Deduplicates. Returns a
composite slice that's richer than any single algorithm.

## The Synthesis Step

After selecting a slice, the skill feeds the zee bodies to the LLM with
this prompt framework:

```
You are a character query engine. You've been given a random slice of
a person's zeemap — their decisions, beliefs, ideas, and research.

These zees are a fingerprint. Not a complete picture, but a window.

From this slice:
1. What pattern do you see that the person might not see?
2. What connection exists between these zees that wasn't explicit?
3. What should this person explore next, based on what's here?
4. What would their digital clone say about this?

Be specific. Reference the actual zees. Don't generalize.
```

## Output Modes

### Text (default)
The synthesis as markdown. Includes the slice metadata (which algorithms,
which zees) and the synthesis.

### Audio (`--audio`)
Generate a TTS voice memo of the synthesis. The clone speaks.

### Visual (`--visual`)
Generate an image that represents the character slice — a visual
fingerprint of this moment in the zee graph. Uses image generation.

### Sonification (future)
Map zee properties to MIDI: type -> instrument, zone -> key, body length
-> pitch, tags -> harmony. Tools: MIDITime, Sonic Pi. A character slice
becomes a melody. At 1000 zees, the zeemap becomes a song.

## CLI Usage

```bash
# Full hybrid query with synthesis
~/.hermes/skills/productivity/zeemap-muse/scripts/muse.py --mode hybrid --synthesize

# Just show the slice, no synthesis
~/.hermes/skills/productivity/zeemap-muse/scripts/muse.py --mode entropy --count 5

# Walk from a specific tag
~/.hermes/skills/productivity/zeemap-muse/scripts/muse.py --mode walk --start-tag hermes --depth 3

# Bridge two zones
~/.hermes/skills/productivity/zeemap-muse/scripts/muse.py --mode bridge --zone-a philosophy --zone-b fragrance

# Belief cluster only
~/.hermes/skills/productivity/zeemap-muse/scripts/muse.py --mode beliefs --count 5

# With audio output flag
~/.hermes/skills/productivity/zeemap-muse/scripts/muse.py --mode hybrid --synthesize --audio

# With visual output flag
~/.hermes/skills/productivity/zeemap-muse/scripts/muse.py --mode hybrid --synthesize --visual

# JSON output for piping
~/.hermes/skills/productivity/zeemap-muse/scripts/muse.py --mode hybrid --count 6 --json --synthesize
```

## Scaling Behavior

| Zees  | Best algorithms           | Notes |
|-------|---------------------------|-------|
| 10    | beliefs, constellation    | Graph too thin for walks |
| 34    | all (current)             | Walk chains are short (3-4), entropy works |
| 100   | all                       | Walk chains deepen, zone bridges get interesting |
| 1000  | all + custom queries      | Graph dense enough for multi-hop traversal, subgraph extraction |

## Pitfalls

- **Don't over-interpret small slices.** At 34 zees, a 5-zee slice is
  15% of the corpus. That's a snapshot, not a portrait. Say so.
- **Don't flatten beliefs into "insights."** A belief like "the garden IS
  the seed" is not the same as "Zak likes gardening." Respect the
  original language.
- **Don't generate generic synthesis.** If the synthesis could apply to
  anyone, it failed. Reference specific zees, specific tags, specific
  connections.
- **Don't run synthesis without showing the slice first.** The user
  should see what the algorithm picked before the LLM interprets it.
- **Don't assume the clone is the person.** The clone is a query engine
  over the artifacts. It's augmented, not replicated.

## Future Directions

- **Temporal queries:** "What was I thinking about in mid-April?"
- **Drift detection:** "How has my thinking changed since the first zee?"
- **Gap analysis:** "What's missing from my graph?"
- **Seed evolution:** Track how a single idea zee connects to decisions
  and beliefs over time
- **Sonification:** Map zee data to MIDI — type to instrument, zone to
  key, body length to pitch. The zeemap as a song.
- **Multi-modal character prints:** Audio narration + visual fingerprint +
  text as a single artifact
- **Behavioral fingerprinting:** Adapt the arXiv diagnostic prompt
  approach (21 prompts, 4 categories) for human zee profiles
