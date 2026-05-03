"""Tests for the pure-function dispatcher.

The dispatcher takes a parent zee dict + optional override and returns
(mode_name, reason). No I/O; no DB; no LLM. Pure function.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

import dispatcher  # noqa: E402


# --- helper ---

def _zee(**overrides):
    base = {
        "uuid": "00000000-0000-0000-0000-000000000001",
        "title": "test zee",
        "type": "seed",
        "zone": "tech",
        "tags": ["test"],
        "what": "A clear what.",
        "why": "A clear why.",
        "body": "...",
    }
    base.update(overrides)
    return base


# --- dispatch tests ---

def test_belief_routes_to_counter():
    mode, reason = dispatcher.pick_mode(_zee(type="belief"))
    assert mode == "counter"
    assert "belief" in reason

def test_idea_routes_to_concretize():
    mode, _ = dispatcher.pick_mode(_zee(type="idea"))
    assert mode == "concretize"

def test_question_falls_back_to_expand_in_v01():
    mode, _ = dispatcher.pick_mode(_zee(type="question"))
    assert mode == "expand"

def test_decision_falls_back_to_expand_in_v01():
    mode, _ = dispatcher.pick_mode(_zee(type="decision"))
    assert mode == "expand"

def test_research_falls_back_to_expand_in_v01():
    mode, _ = dispatcher.pick_mode(_zee(type="research"))
    assert mode == "expand"

def test_unknown_type_falls_back_to_expand():
    mode, _ = dispatcher.pick_mode(_zee(type="something-new"))
    assert mode == "expand"


# --- enrich-wins tests ---

def test_empty_what_triggers_enrich_even_for_belief():
    mode, reason = dispatcher.pick_mode(_zee(type="belief", what=""))
    assert mode == "enrich"
    assert "metadata" in reason or "thin" in reason

def test_empty_why_triggers_enrich():
    mode, _ = dispatcher.pick_mode(_zee(type="idea", why=""))
    assert mode == "enrich"

def test_unclear_marker_triggers_enrich():
    mode, _ = dispatcher.pick_mode(_zee(why="unclear — see body"))
    assert mode == "enrich"

def test_tentative_marker_triggers_enrich():
    mode, _ = dispatcher.pick_mode(_zee(what="tentative: maybe X"))
    assert mode == "enrich"

def test_not_yet_articulated_marker_triggers_enrich():
    mode, _ = dispatcher.pick_mode(_zee(why="not yet articulated"))
    assert mode == "enrich"

def test_tbd_marker_triggers_enrich():
    mode, _ = dispatcher.pick_mode(_zee(what="tbd"))
    assert mode == "enrich"


# --- override tests ---

def test_override_takes_precedence():
    mode, reason = dispatcher.pick_mode(_zee(type="belief"), override="expand")
    assert mode == "expand"
    assert "override" in reason

def test_unknown_override_raises():
    with pytest.raises(ValueError):
        dispatcher.pick_mode(_zee(), override="not-a-real-mode")


# --- leaf type lookup ---

def test_leaf_type_for_counter_is_note():
    assert dispatcher.leaf_type_for("counter", parent_type="belief") == "note"

def test_leaf_type_for_concretize_is_idea():
    assert dispatcher.leaf_type_for("concretize", parent_type="idea") == "idea"

def test_leaf_type_for_enrich_matches_parent():
    assert dispatcher.leaf_type_for("enrich", parent_type="research") == "research"

def test_leaf_type_for_expand_matches_parent():
    assert dispatcher.leaf_type_for("expand", parent_type="seed") == "seed"
