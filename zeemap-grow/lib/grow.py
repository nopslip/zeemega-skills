#!/usr/bin/env python3
"""zeemap-grow — grow a leaf from a single zee.

Reads parent zee, dispatches to a mode based on parent state, renders
the prompt template, and emits JSON for the calling agent.

The agent (Hermes/Claude) feeds `prompt` to the LLM, takes the
response as the leaf body, and shells out to write_zee.py with the
fields in `suggested_write` plus title/what/why extracted from the
LLM response.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB_DIR))

import dispatcher  # noqa: E402
import prompt as prompt_mod  # noqa: E402
import reader  # noqa: E402

PROMPTS_DIR = LIB_DIR.parent / "prompts"


def main():
    parser = argparse.ArgumentParser(description="Grow a leaf zee from a parent")
    parser.add_argument(
        "identifier",
        help="Parent zee uuid or slug-style filename (without .md)",
    )
    parser.add_argument(
        "--mode",
        help="Override the dispatcher (must match a key in dispatch.yaml modes)",
        default=None,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON only (default; flag exists for symmetry with muse)",
    )
    args = parser.parse_args()

    try:
        parent = reader.get_parent(args.identifier)
    except LookupError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 3

    mode, reason = dispatcher.pick_mode(parent, override=args.mode)
    leaf_type = dispatcher.leaf_type_for(mode, parent_type=parent["type"])

    template_path = PROMPTS_DIR / f"{mode}.md"
    if not template_path.exists():
        print(
            json.dumps({"error": f"no prompt template for mode={mode!r}"}),
            file=sys.stderr,
        )
        return 4

    rendered_prompt = prompt_mod.render(template_path, parent)

    output = {
        "mode": mode,
        "reason": reason,
        "parent": {
            "uuid": parent["uuid"],
            "title": parent["title"],
            "type": parent["type"],
            "zone": parent["zone"],
            "tags": parent["tags"],
            "what": parent["what"],
            "why": parent["why"],
        },
        "prompt": rendered_prompt,
        "suggested_write": {
            "type": leaf_type,
            "zone": parent["zone"],
            "skill": "zeemap-grow",
            "seeded_from": parent["uuid"],
        },
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
