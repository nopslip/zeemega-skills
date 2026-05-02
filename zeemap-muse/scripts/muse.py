#!/usr/bin/env python3
"""
Zeemega — Character Query Engine
Samples the zeemap graph to extract personality slices
and surface new ideas, media, and content.

Usage:
  zeemega.py --mode hybrid --synthesize
  zeemega.py --mode walk --start-tag hermes --depth 3
  zeemega.py --mode bridge --zone-a philosophy --zone-b tech
  zeemega.py --mode entropy --count 5 --json
  zeemega.py --mode beliefs --count 5 --synthesize --audio
  zeemega.py --mode constellation --types belief,idea,research --per-type 2
"""

import argparse
import json
import os
import random
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

# ── Config ──
ZEE_DIR = os.environ.get(
    "ZEEMAP_DATA_DIR",
    os.path.expanduser("~/.hermes/skills/productivity/zeemap/data/"),
)

# ── Parser ──

def parse_zee(filepath):
    """Parse a zee markdown file into a dict."""
    with open(filepath) as f:
        raw = f.read()

    lines = raw.split("\n")
    fm = {}
    in_fm = False
    body_lines = []
    for line in lines:
        if line.strip() == "---" and not in_fm:
            in_fm = True
            continue
        if line.strip() == "---" and in_fm:
            in_fm = False
            continue
        if in_fm and ":" in line:
            key = line.split(":")[0].strip()
            val = ":".join(line.split(":")[1:]).strip().strip('"').strip("'")
            fm[key] = val
        elif not in_fm:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()
    raw_tags = fm.get("tags", "[]")
    tags = [
        t.strip().strip("'\"")
        for t in raw_tags.strip("[]").split(",")
        if t.strip().strip("'\"")
    ]

    return {
        "path": str(filepath),
        "filename": Path(filepath).name,
        "zone": fm.get("zone", "unknown").strip("'\""),
        "type": fm.get("type", "unknown").strip("'\""),
        "title": fm.get("title", "untitled").strip("'\""),
        "tags": tags,
        "what": fm.get("what", "").strip("'\""),
        "why": fm.get("why", "").strip("'\""),
        "body": body,
        "body_length": len(body),
        "created": fm.get("created", fm.get("date", "")),
    }


def load_zees():
    """Load all zees from the data directory."""
    zee_dir = Path(ZEE_DIR)
    if not zee_dir.exists():
        print(f"Error: ZEE_DIR not found: {ZEE_DIR}", file=sys.stderr)
        sys.exit(1)

    files = sorted(zee_dir.glob("*.md"))
    zees = [parse_zee(f) for f in files]

    for i, z in enumerate(zees):
        z["idx"] = i

    return zees


def build_indexes(zees):
    """Build graph indexes from zee list."""
    tag_idx = {}
    zone_idx = {}
    type_idx = {}

    for i, z in enumerate(zees):
        zone_idx.setdefault(z["zone"], set()).add(i)
        type_idx.setdefault(z["type"], set()).add(i)
        for t in z["tags"]:
            tag_idx.setdefault(t, set()).add(i)

    co_occur = Counter()
    for z in zees:
        for a, b in combinations(sorted(z["tags"]), 2):
            co_occur[(a, b)] += 1

    return {
        "tag": tag_idx,
        "zone": zone_idx,
        "type": type_idx,
        "co_occur": co_occur,
    }


# ── Algorithms ──

def algo_walk(zees, indexes, start_tag=None, depth=3, branch=2):
    """Random walk through the tag graph. Follows tag edges to build a tree."""
    tag_idx = indexes["tag"]

    if start_tag and start_tag in tag_idx:
        start = random.choice(list(tag_idx[start_tag]))
    else:
        start = random.randrange(len(zees))

    visited = set()
    result = []

    def visit(idx, d):
        if idx in visited or d > depth:
            return
        visited.add(idx)
        z = zees[idx]
        result.append({"zee": z, "depth": d, "via": "walk"})
        neighbors = set()
        for t in z["tags"]:
            neighbors |= tag_idx.get(t, set())
        neighbors -= visited
        picks = random.sample(list(neighbors), min(branch, len(neighbors)))
        for ni in picks:
            visit(ni, d + 1)

    visit(start, 0)
    return result


def algo_constellation(zees, indexes, types=None, per_type=2):
    """Pick N from each type for a balanced personality slice."""
    if types is None:
        types = ["belief", "idea", "research"]
    type_idx = indexes["type"]
    result = []
    for t in types:
        pool = list(type_idx.get(t, set()))
        picks = random.sample(pool, min(per_type, len(pool)))
        for idx in picks:
            result.append({"zee": zees[idx], "via": f"type:{t}"})
    return result


def algo_bridge(zees, indexes, zone_a, zone_b, per_zone=2):
    """Cross-pollinate two zones that don't normally connect."""
    zone_idx = indexes["zone"]
    result = []

    for zone in [zone_a, zone_b]:
        pool = list(zone_idx.get(zone, set()))
        picks = random.sample(pool, min(per_zone, len(pool)))
        for idx in picks:
            result.append({"zee": zees[idx], "via": f"zone:{zone}"})

    # Find bridging tags (tags that appear in both zones)
    tags_a = set()
    tags_b = set()
    for idx in zone_idx.get(zone_a, set()):
        tags_a |= set(zees[idx]["tags"])
    for idx in zone_idx.get(zone_b, set()):
        tags_b |= set(zees[idx]["tags"])
    bridge_tags = tags_a & tags_b

    return result, bridge_tags


def algo_beliefs(zees, indexes, count=5):
    """Pull beliefs and ideas — the core of identity."""
    type_idx = indexes["type"]
    pool = list(type_idx.get("belief", set()) | type_idx.get("idea", set()))
    picks = random.sample(pool, min(count, len(pool)))
    return [{"zee": zees[idx], "via": "belief/idea"} for idx in picks]


def algo_entropy(zees, indexes, count=5):
    """Weighted random by tag rarity. Surfaces the surprising, not the obvious."""
    tag_idx = indexes["tag"]
    tag_freq = {t: len(idxs) for t, idxs in tag_idx.items()}

    weights = []
    for z in zees:
        rarity = sum(1.0 / tag_freq[t] for t in z["tags"] if t in tag_freq)
        weights.append(max(rarity, 0.01))

    # Weighted sample without replacement
    available = list(range(len(zees)))
    weights_copy = list(weights)
    picks = []

    for _ in range(min(count, len(available))):
        if not available:
            break
        s = sum(weights_copy)
        if s == 0:
            break
        normed = [w / s for w in weights_copy]
        chosen = random.choices(available, weights=normed, k=1)[0]
        picks.append(chosen)
        idx = available.index(chosen)
        available.pop(idx)
        weights_copy.pop(idx)

    return [{"zee": zees[idx], "via": "entropy"} for idx in picks]


def algo_hybrid(zees, indexes, count=7):
    """Run 2-3 algorithms and merge. Default mode."""
    n = len(zees)
    result = []

    # Always include beliefs — the core
    result += algo_beliefs(zees, indexes, count=2)

    # Add entropy if enough tags
    if n >= 20:
        result += algo_entropy(zees, indexes, count=2)

    # Add walk if enough zees
    if n >= 15:
        result += algo_walk(zees, indexes, depth=2, branch=1)

    # Deduplicate by filename
    seen = set()
    deduped = []
    for item in result:
        fn = item["zee"]["filename"]
        if fn not in seen:
            seen.add(fn)
            deduped.append(item)

    return deduped[:count]


# ── Synthesis ──

SYNTHESIS_PROMPT = """You are a character query engine. You've been given a random slice of
a person's zeemap — their decisions, beliefs, ideas, and research.

These zees are a fingerprint. Not a complete picture, but a window into how this person thinks.

From this slice:
1. **Hidden pattern** — What connects these zees that the person might not see?
2. **Unexpected bridge** — What link exists between two zees here that wasn't explicit?
3. **Next exploration** — Based on what's here, what should this person explore next?
4. **Clone's take** — If this person's digital clone could say one thing about this slice, what?

Be specific. Reference the actual zee titles. Don't generalize. Don't be safe.
"""


def format_slice_text(result, zees_total):
    """Format a slice as readable text."""
    lines = []
    lines.append(f"Character slice: {len(result)} zees from {zees_total} total\n")
    lines.append("---\n")
    for item in result:
        z = item["zee"]
        via = item.get("via", "")
        lines.append(f"[{z['zone']}/{z['type']}] {z['title']}")
        if via:
            lines.append(f"  selected via: {via}")
        if z["what"]:
            lines.append(f"  what: {z['what']}")
        if z["tags"]:
            lines.append(f"  tags: {', '.join(z['tags'])}")
        lines.append("")
    return "\n".join(lines)


def format_synthesis_prompt(result, zees_total):
    """Build the full synthesis prompt for the LLM."""
    slice_text = format_slice_text(result, zees_total)

    bodies = []
    for item in result:
        z = item["zee"]
        body_preview = z["body"][:800] if z["body"] else "(no body)"
        bodies.append(f"### {z['title']}\n{body_preview}")

    return f"""{SYNTHESIS_PROMPT}

## Slice metadata
{slice_text}

## Zee bodies (truncated)
{"---".join(bodies)}
"""


# ── Output ──

def print_json(result, zees_total, mode, args):
    """Output as JSON."""
    output = {
        "mode": mode,
        "total_zees": zees_total,
        "slice_size": len(result),
        "seed": args.seed,
        "slice": [
            {
                "title": item["zee"]["title"],
                "zone": item["zee"]["zone"],
                "type": item["zee"]["type"],
                "tags": item["zee"]["tags"],
                "what": item["zee"]["what"],
                "via": item.get("via", ""),
                "path": item["zee"]["path"],
            }
            for item in result
        ],
    }
    if args.synthesize:
        output["synthesis_prompt"] = format_synthesis_prompt(result, zees_total)
    print(json.dumps(output, indent=2))


def print_human(result, zees_total, mode, args):
    """Output for human reading."""
    print(f"{'='*60}")
    print(f"Zeemega — Character Query ({mode})")
    print(f"{'='*60}")
    print(f"Slice: {len(result)} zees from {zees_total} total")
    if args.seed is not None:
        print(f"Seed: {args.seed}")
    print()

    for item in result:
        z = item["zee"]
        via = item.get("via", "")
        depth = item.get("depth", 0)
        indent = "  " * depth
        print(f"{indent}[{z['zone']}/{z['type']}] {z['title']}")
        if via:
            print(f"{indent}  via: {via}")
        if z["what"]:
            what = z["what"][:120]
            print(f"{indent}  -> {what}")
        if z["tags"]:
            print(f"{indent}  tags: {', '.join(z['tags'][:6])}")

    print()

    if args.synthesize:
        print(f"{'='*60}")
        print("SYNTHESIS PROMPT (feed to LLM)")
        print(f"{'='*60}")
        print(format_synthesis_prompt(result, zees_total))


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description="Zeemega — Character Query Engine")
    parser.add_argument(
        "--mode",
        choices=["walk", "constellation", "bridge", "beliefs", "entropy", "hybrid"],
        default="hybrid",
        help="Query algorithm (default: hybrid)",
    )
    parser.add_argument("--count", type=int, default=5, help="Number of zees in slice")
    parser.add_argument("--start-tag", help="Starting tag for walk mode")
    parser.add_argument("--depth", type=int, default=3, help="Walk depth")
    parser.add_argument("--branch", type=int, default=2, help="Walk branch factor")
    parser.add_argument("--zone-a", help="First zone for bridge mode")
    parser.add_argument("--zone-b", help="Second zone for bridge mode")
    parser.add_argument("--types", help="Comma-separated types for constellation mode")
    parser.add_argument("--per-type", type=int, default=2, help="Per-type count for constellation")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--synthesize", action="store_true", help="Include synthesis prompt")
    parser.add_argument("--audio", action="store_true", help="Flag: generate audio output")
    parser.add_argument("--visual", action="store_true", help="Flag: generate visual output")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
    else:
        random.seed()

    zees = load_zees()
    if not zees:
        print("No zees found.", file=sys.stderr)
        sys.exit(1)

    indexes = build_indexes(zees)

    mode = args.mode
    if mode == "walk":
        result = algo_walk(zees, indexes, start_tag=args.start_tag, depth=args.depth, branch=args.branch)
    elif mode == "constellation":
        types = args.types.split(",") if args.types else None
        result = algo_constellation(zees, indexes, types=types, per_type=args.per_type)
    elif mode == "bridge":
        zone_a = args.zone_a or random.choice(list(indexes["zone"].keys()))
        zone_b = args.zone_b or random.choice([z for z in indexes["zone"] if z != zone_a])
        result, bridge_tags = algo_bridge(zees, indexes, zone_a, zone_b)
        if not args.json:
            print(f"Bridging: {zone_a} <-> {zone_b}")
            print(f"Bridge tags: {bridge_tags}\n")
    elif mode == "beliefs":
        result = algo_beliefs(zees, indexes, count=args.count)
    elif mode == "entropy":
        result = algo_entropy(zees, indexes, count=args.count)
    elif mode == "hybrid":
        result = algo_hybrid(zees, indexes, count=args.count)

    if args.json:
        print_json(result, len(zees), mode, args)
    else:
        print_human(result, len(zees), mode, args)

    if args.audio:
        print("\n[AUDIO_REQUESTED]")
    if args.visual:
        print("\n[VISUAL_REQUESTED]")


if __name__ == "__main__":
    main()
