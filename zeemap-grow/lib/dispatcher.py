"""Pure-function dispatcher for zeemap-grow.

Reads dispatch.yaml at import time and picks a mode based on parent
state. No I/O beyond reading the YAML file once.
"""

from __future__ import annotations

from pathlib import Path

import yaml

DISPATCH_YAML = Path(__file__).resolve().parent.parent / "dispatch.yaml"

_THIN_MARKERS = ("unclear", "not yet articulated", "tentative", "tbd")


def _is_thin(value: str) -> bool:
    if not value or not value.strip():
        return True
    lower = value.strip().lower()
    return any(lower.startswith(m) or lower == m for m in _THIN_MARKERS)


def _load_dispatch() -> dict:
    return yaml.safe_load(DISPATCH_YAML.read_text())


def _evaluate_condition(condition: str, parent: dict) -> bool:
    if condition == "metadata_thin":
        return _is_thin(parent.get("what", "")) or _is_thin(parent.get("why", ""))
    if condition.startswith("type_is_"):
        target = condition.removeprefix("type_is_")
        return parent.get("type") == target
    if condition == "always":
        return True
    raise ValueError(f"unknown dispatch condition: {condition}")


def pick_mode(parent: dict, override: str | None = None) -> tuple[str, str]:
    """Return (mode_name, reason) for this parent zee.

    If `override` is given, return it directly (after validating it
    matches a known mode). Otherwise walk the trigger list in order
    and return the first match.
    """
    config = _load_dispatch()
    known_modes = set(config["modes"].keys())

    if override is not None:
        if override not in known_modes:
            raise ValueError(
                f"unknown mode override: {override!r}; "
                f"known modes: {sorted(known_modes)}"
            )
        return override, f"override: --mode {override}"

    for trigger in config["triggers"]:
        if _evaluate_condition(trigger["condition"], parent):
            return trigger["mode"], _reason_for(trigger["condition"], parent)

    raise RuntimeError(
        "no trigger matched and no `always` fallback in dispatch.yaml — "
        "config is malformed"
    )


def _reason_for(condition: str, parent: dict) -> str:
    if condition == "metadata_thin":
        return "metadata thin (what or why empty/unclear)"
    if condition.startswith("type_is_"):
        return f"parent type={parent.get('type')}; metadata complete"
    if condition == "always":
        return f"fallback (parent type={parent.get('type')!r})"
    return condition


def leaf_type_for(mode: str, *, parent_type: str) -> str:
    """Look up the leaf type for a mode in dispatch.yaml.

    Returns parent_type when the table says `same_as_parent`.
    """
    config = _load_dispatch()
    for trigger in config["triggers"]:
        if trigger["mode"] == mode:
            lt = trigger["leaf_type"]
            return parent_type if lt == "same_as_parent" else lt
    raise ValueError(f"mode {mode!r} not found in dispatch.yaml triggers")
