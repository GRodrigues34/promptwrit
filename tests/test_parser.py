"""Tests for XML context scoping, active tag legend, auto-pluralization, and clean copy."""

from promptwrit.parser import (
    allowed_tags_for_context,
    apply_auto_pluralization,
    clean_prompt_for_copy,
    expand_tag_snippet,
    extract_active_tags,
    get_tag_stack_at_cursor,
)
from promptwrit.schema import default_config


def test_context_scoping_root_vs_nested() -> None:
    cfg = default_config()
    text = "<FEATURE>\n  <OBJECTIVE>Build X</OBJECTIVE>\n  <"
    stack_inside = get_tag_stack_at_cursor(text, len(text))
    assert stack_inside == ["FEATURE"]

    allowed_inside = {t.name for t in allowed_tags_for_context(stack_inside, cfg)}
    assert "OBJECTIVE" in allowed_inside
    assert "FEATURE" not in allowed_inside
    assert "BUG" not in allowed_inside

    allowed_root = {t.name for t in allowed_tags_for_context([], cfg)}
    assert "FEATURE" in allowed_root
    assert "OBJECTIVE" in allowed_root


def test_extract_active_tags_skips_plurals_and_marks_custom() -> None:
    cfg = default_config()
    text = (
        "<FEATURES>\n"
        "  <FEATURE>\n"
        "    <OBJECTIVE>One</OBJECTIVE>\n"
        "    <MY_CUSTOM>Hi</MY_CUSTOM>\n"
        "  </FEATURE>\n"
        "  <FEATURE>\n"
        "    <OBJECTIVE>Two</OBJECTIVE>\n"
        "  </FEATURE>\n"
        "</FEATURES>"
    )
    active = extract_active_tags(text, cfg)
    names = [name for name, _ in active]
    assert names == ["FEATURE", "OBJECTIVE", "MY_CUSTOM"]
    assert dict(active)["MY_CUSTOM"] == "(custom)"


def test_expand_tag_snippet_respects_templates_toggle() -> None:
    cfg = default_config()
    feature = cfg.tag_map()["FEATURE"]

    cfg.templates_enabled = True
    expanded_on, stops_on = expand_tag_snippet(feature, cfg)
    assert "<OBJECTIVE>" in expanded_on
    assert "<EXAMPLE>" in expanded_on
    assert len(stops_on) == 5

    cfg.templates_enabled = False
    expanded_off, stops_off = expand_tag_snippet(feature, cfg)
    assert expanded_off == f"<FEATURE>{feature.description}</FEATURE>"
    assert len(stops_off) == 1


def test_auto_pluralization_wraps_and_unwraps() -> None:
    cfg = default_config()
    two_features = "<FEATURE>\n  <OBJECTIVE>A</OBJECTIVE>\n</FEATURE>\n<FEATURE>\n  <OBJECTIVE>B</OBJECTIVE>\n</FEATURE>"
    wrapped = apply_auto_pluralization(two_features, cfg)
    assert wrapped.startswith("<FEATURES>")
    assert wrapped.endswith("</FEATURES>")

    # Remove second feature -> should unwrap back to singular <FEATURE>.
    single_inside = "<FEATURES>\n  <FEATURE>\n    <OBJECTIVE>A</OBJECTIVE>\n  </FEATURE>\n</FEATURES>"
    unwrapped = apply_auto_pluralization(single_inside, cfg)
    assert unwrapped.startswith("<FEATURE>")
    assert "<FEATURES>" not in unwrapped


def test_clean_prompt_for_copy_strips_hints_and_empty_tags() -> None:
    cfg = default_config()
    hints = {t.description for t in cfg.tags}
    raw = (
        "<FEATURE>\n"
        "  <OBJECTIVE>Add JWT rotation</OBJECTIVE>\n"
        "  <CONTEXT>Repo state, background, or #file paths</CONTEXT>\n"
        "  <EXAMPLE></EXAMPLE>\n"
        "</FEATURE>"
    )
    cleaned = clean_prompt_for_copy(raw, hints, strip_empty_tags=True)
    assert "<OBJECTIVE>Add JWT rotation</OBJECTIVE>" in cleaned
    assert "<CONTEXT>" not in cleaned
    assert "<EXAMPLE>" not in cleaned
