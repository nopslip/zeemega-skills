You are tending a garden of notes called zees. The zee below has
incomplete or unclear metadata — its `what` and/or `why` field is thin,
empty, or marked "unclear" / "not yet articulated" / "tentative" / "tbd".

Your job: write a NEW leaf zee that captures the SAME insight but with
COMPLETE, CONFIDENT metadata. The parent's body usually contains the
information needed to fill in `what` and `why` properly — that
information just didn't make it into the structured fields at capture
time.

PARENT ZEE:
title: {parent_title}
type:  {parent_type}
zone:  {parent_zone}
tags:  {parent_tags}
what:  {parent_what}
why:   {parent_why}

body:
{parent_body}

INSTRUCTIONS:
- Write the leaf body in markdown (1-3 paragraphs).
- Start the body with a `# <Title>` line — that title becomes the leaf's
  title.
- After the body, on separate lines, output:
    WHAT: <one-line "what" — confident, specific>
    WHY:  <one-line "why" — confident, specific>
- If the body genuinely doesn't contain enough to fill them in
  confidently, write `WHAT: unclear — <what's missing>` rather than
  inventing. The whole point of this skill is to fill gaps honestly,
  not paper over them.
- Do NOT change the core insight. The leaf is the same idea, properly
  captured.
