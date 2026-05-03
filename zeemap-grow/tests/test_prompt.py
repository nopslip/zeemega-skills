"""Tests for the prompt renderer.

The renderer takes a template path + a parent zee dict and returns the
rendered prompt string with parent fields injected. Pure function.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

import prompt  # noqa: E402


def _zee(**overrides):
    base = {
        "uuid": "abc-123",
        "title": "Why we chose Docker per instance",
        "type": "decision",
        "zone": "tech",
        "tags": ["docker", "isolation"],
        "what": "One container per bot.",
        "why": "Gateway exploit can't touch other bots.",
        "body": "Detail prose body here.",
    }
    base.update(overrides)
    return base


def _tmpl(tmp_path):
    p = tmp_path / "test_template.md"
    p.write_text(
        "PARENT TITLE: {parent_title}\n"
        "PARENT TYPE: {parent_type}\n"
        "PARENT WHAT: {parent_what}\n"
        "PARENT WHY: {parent_why}\n"
        "PARENT BODY: {parent_body}\n"
    )
    return p


def test_render_injects_all_fields(tmp_path):
    rendered = prompt.render(_tmpl(tmp_path), _zee())
    assert "PARENT TITLE: Why we chose Docker per instance" in rendered
    assert "PARENT TYPE: decision" in rendered
    assert "PARENT WHAT: One container per bot." in rendered
    assert "PARENT WHY: Gateway exploit can't touch other bots." in rendered
    assert "PARENT BODY: Detail prose body here." in rendered


def test_render_handles_empty_what(tmp_path):
    rendered = prompt.render(_tmpl(tmp_path), _zee(what=""))
    # Empty value should render as empty string, not "None" or KeyError.
    assert "PARENT WHAT: \n" in rendered


def test_render_handles_missing_field(tmp_path):
    parent = _zee()
    del parent["why"]
    rendered = prompt.render(_tmpl(tmp_path), parent)
    # Missing key should render as empty string, not KeyError.
    assert "PARENT WHY: \n" in rendered


def test_render_template_without_placeholders_is_pass_through(tmp_path):
    p = tmp_path / "no_placeholder.md"
    p.write_text("This template has no placeholders.")
    rendered = prompt.render(p, _zee())
    assert rendered == "This template has no placeholders."
