"""Prompt renderer for zeemap-grow.

render(template_path, parent_zee) -> str

Templates use Python's str.format_map with a defaultdict that returns ''
for missing keys, so a missing parent field renders as empty string
rather than raising KeyError.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path


_FIELD_MAP = {
    "title": "parent_title",
    "type": "parent_type",
    "zone": "parent_zone",
    "tags": "parent_tags",
    "what": "parent_what",
    "why": "parent_why",
    "body": "parent_body",
    "uuid": "parent_uuid",
}


def _flatten(parent: dict) -> dict:
    out = defaultdict(str)
    for key, placeholder in _FIELD_MAP.items():
        value = parent.get(key, "")
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        out[placeholder] = "" if value is None else str(value)
    return out


def render(template_path: Path, parent: dict) -> str:
    template = Path(template_path).read_text()
    return template.format_map(_flatten(parent))
