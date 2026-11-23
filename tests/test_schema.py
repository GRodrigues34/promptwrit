"""Tests for schema loading, saving, and defaults."""

from pathlib import Path

from promptwrit.schema import TagDef, default_config, load_config, save_config


def test_default_config_has_expected_main_and_complementary_tags() -> None:
    cfg = default_config()
    main_names = {t.name for t in cfg.main_tags()}
    comp_names = {t.name for t in cfg.complementary_tags()}

    assert main_names == {
        "FEATURE",
        "BUG",
        "UPDATE",
        "REFACTOR",
        "TEST",
        "REVIEW",
        "PLAN",
        "DEBUG",
        "DOCS",
        "PROMPT",
    }
    assert comp_names == {
        "OBJECTIVE",
        "CONTEXT",
        "EXAMPLE",
        "CONSTRAINTS",
        "EXPECTED",
        "ACTUAL",
        "VERIFICATION",
        "OUTPUT",
    }


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    cfg = default_config()
    cfg.templates_enabled = False
    cfg.indent_spaces = 4
    cfg.tags.append(TagDef(name="PERF", kind="main", description="Optimize performance"))

    save_config(cfg, cfg_file)
    loaded = load_config(cfg_file)

    assert loaded.templates_enabled is False
    assert loaded.indent_spaces == 4
    assert "PERF" in loaded.tag_map()
    assert loaded.tag_map()["PERF"].plural == "PERFS"
