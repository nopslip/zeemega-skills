---
name: zeemap-intro
author: Zak
description: First-run guided experience for new Zeemega users. Use ONLY when the user explicitly asks what Zeemega is or for a tour — phrases like "what is zeemega", "what is this", "intro me", "give me the tour", "show me what you do", "explain zeemega", "I'm new here, walk me through this", "onboard me", "teach me what you can do". Do NOT trigger on bare greetings ("hi", "hello", "yo"), generic acknowledgments ("thanks", "ok"), or any message where the user is already pursuing a specific task. If a more specific skill matches (zeemap to save a note, zeemap-fetch to find one) prefer that skill.
version: 0.1.0
platforms: [linux]
required_environment_variables: [ZEEMAP_STORE, DATABASE_URL, HERMES_OWNER_ID]
metadata:
  hermes:
    tags: [onboarding, education, first-run, demo]
    category: productivity
---

# Zeemega-intro — first-run guided experience

This skill exists for one moment in a user's life with Zeemega: the
first time they ask "what is this thing?". Most of them have never
talked to an agent before. They are coming from ChatGPT, from
Google. They have not yet *felt* a system that takes a real-world
goal and chases it across multiple steps with judgment.

Your job in this skill is not to explain that. It's to make them
feel it. The whole skill is a demo — the experience teaches what the
words can't.

## When to use this skill

Trigger only on explicit asks. The user has to be reaching for an
intro, not just saying hi.

Yes:
- "what is zeemega" / "what is this"
- "intro me" / "onboard me" / "teach me"
- "give me the tour" / "show me what you can do"
- "explain zeemega" / "walk me through this"
- "I'm new here"

No:
- Bare greetings: "hi", "hello", "yo", "good morning"
- Generic acknowledgments: "thanks", "ok", "cool", "got it"
- Already-on-task messages — if they're researching, planting a
  note, or doing anything specific, that is not the intro moment.
- Repeats — if they've been through this before (look for a meta-
  zone zee tagged `first-zee` in their library before starting),
  ask: *"Want a fresh round on something new, or are you looking
  for something specific?"* Don't replay the whole arc.

If you're not sure whether the user wants the intro, ask one
clarifying line ("want the quick tour, or are you after something
specific?") rather than guessing.

## The conversation arc

Five beats. Don't number them in chat — that breaks the warmth.
Just feel them.

### 1. Welcome + one real question

Short. Conversational. No bullet list of features.

> Hey — welcome to Zeemega. Quick question to get us going:
> what's something you've been meaning to look into but haven't
> had time for? Not "send an email" — something real. A decision
> you keep circling, a place you might move, a person you want to
> look up, gear you'd buy if you knew which one.

If they answer with a clear topic → go to beat 3 directly.

### 2. If they hesitate, offer three flavored starters

Don't read a generic feature list. Offer three concrete *shapes*
that hint at the agent's range:

> No worries — three places people often start:
> - A place they're curious about — a town, a neighborhood, a
>   country.
> - A thing they'd buy if they knew the right one — a piece of
>   gear, a tool, a service.
> - A person or company they've been meaning to look into.
>
> Or just throw me anything you've been wondering about.

The list isn't the point — giving them permission to bring something
*real* instead of testing you is the point.

### 3. Run it for real

This is the only beat that matters. Whatever they brought, take it
seriously and *do the work*.

- **Research-shaped** ("tell me about Lisbon") → `web_search`. Pull
  2-4 useful sources, synthesize, name what surprised you.
- **Decision-shaped** ("which laptop should I buy") → frame the
  tradeoffs, name the variables that should drive the choice, end
  with a recommendation or a clear "here's how I'd decide".
- **Plan-shaped** ("how do I switch careers into product") →
  outline the steps, identify the unknowns, surface what's actually
  hard.
- **Not web-researchable** (private, personal, internal-to-them) →
  don't fake it. Pivot to what you can do: clarify the question,
  surface the variables, propose a way to make progress. Honesty
  here lands harder than performance.

The output should be visibly richer than what they'd get from
typing the same query into Google. Sources matter. Structure
matters. Have a take. Write something they'll actually read — longer
than a chat reply, shorter than an essay. Aim for a length they
might screenshot.

### 4. The pivot — name what just happened

After delivering the result, pivot in 2-3 sentences.

> What I just did was a *skill* — a task with steps, written down
> so it can be re-run, scheduled, or extended. The note version of
> what we just figured out is called a *zee*. I'm going to save
> this as your first zee — that way future-you can ask for it back
> by topic, share it, or build on it.

Don't lecture. Don't define agent vs. chatbot. Don't list every
skill they have. The pivot is one beat, not a chapter.

### 5. Plant the first zee

This is the **secret goal of the whole skill**. The first zee a
user ever sees in their library should make them think *"oh, this
is different."* It needs to be:

- **Titled in their voice**, not yours. If they asked about moving
  to Lisbon, the title is "Lisbon move — what to know before
  visiting", not "Research result for query".
- **Honest about the question they actually asked.** Open the body
  with their original phrasing, then the synthesis.
- **Genuinely useful at re-read.** Six-months-later them should
  still get value.
- **Tagged so we can find this cohort.** Tags MUST include `intro`
  and `first-zee`. Zone is `meta`. Type is usually `note`, but
  `research` is fine if the work was actually research.

Write the zee via the canonical writer — never hand-roll
frontmatter, never `cat > data/*.md`. The script routes through
Postgres in hosted mode; bypassing it makes the zee invisible to
the viewer.

```bash
BODY=$(mktemp --suffix=.md)
cat > "$BODY" << 'BODY_END'
# <title in their voice>

> <their original question, lightly cleaned>

## What I found

<2-4 paragraph synthesis of the research / framing / plan>

## Sources

- <url 1>
- <url 2>

## Worth following up on

- <one or two open questions worth coming back to>
BODY_END

~/.hermes/skills/productivity/zeemap/lib/write_zee.py \
  --title    "<title in their voice>" \
  --body-file "$BODY" \
  --zone     meta \
  --tags     "intro,first-zee,<topic-tag>" \
  --what     "First zee — <their question, one line>." \
  --why      "Planted during zeemap-intro tour as their first artifact." \
  --type     note \
  --skill    zeemap-intro \
  --model    <your model id, e.g. claude-opus-4-7>

rm "$BODY"
```

If `write_zee.py` exits non-zero, surface the error and stop. Don't
fall back to writing a `.md` file directly — that bypasses Postgres
and the zee never appears in the viewer. Exit-code semantics are
documented in `zeemap/SKILL.md`; exit `6` in particular means
re-exec via the venv python, not local-mode fallback.

### 6. Send them off with the link

The script prints the canonical filename on success. Strip the
`.md` and prefix `https://app.zeemega.com/#/z/` to get the in-app
URL. Hand it back warmly:

> Saved as your first zee: <in-app URL>
>
> Two things you can do from here:
> - Say *"find my zee about <topic>"* anytime to pull this back up.
> - Say *"save this"* during any conversation to plant a new zee.
>
> What else are you curious about?

That last line keeps the door open. Most users will keep going —
and now they're not in the intro, they're just *using* it.

## Pitfalls

- **Don't lecture.** If you find yourself explaining "what is an
  agent" abstractly, stop. The whole skill is a demo.
- **Don't dump every feature.** Two pointers (zeemap save / zeemap-
  fetch find) is enough; the rest they'll discover.
- **Don't ask multiple questions in beat 1.** One real question.
- **Don't fake a research result.** If the topic isn't web-
  researchable, say so and pivot. Honesty beats performance here.
- **Don't trigger on greetings.** A bare "hi" is not an intro
  request.
- **Don't write more than one zee.** Intro produces exactly one
  zee. If the conversation goes deeper afterward and earns more
  zees, those are normal `zeemap` writes, not part of intro.
- **Don't try to fix the legacy "zeemap" naming.** The skill dir
  remains `zeemap`; the brand is Zeemega. The mismatch is known
  and out of scope.

## Why this skill exists

People don't yet know what an agent is. They think "search" or
"chat", and Zeemega is neither. The fastest way to teach the
difference is one rich, multi-step result delivered around a topic
they actually care about, sealed by an artifact they can come back
to.

The first zee a user plants is the moment Zeemega goes from
"another AI thing" to "something I have a stake in". This skill's
whole job is to make that moment land.
