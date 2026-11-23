"""Tests for workspace indexing and fuzzy file path matching."""

from pathlib import Path

from promptwrit.indexer import fuzzy_match_files, list_workspace_files, resolve_workspace_root
from promptwrit.schema import default_config


def test_list_workspace_files_and_fuzzy_match(tmp_path: Path) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "architecture.md").write_text("arch", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "old-architecture.md").write_text("old", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "architecture.md").write_text("ignored", encoding="utf-8")

    files = list_workspace_files(tmp_path, respect_gitignore=False)
    assert "backend/architecture.md" in files
    assert "docs/old-architecture.md" in files
    assert "node_modules/architecture.md" not in files

    matches = fuzzy_match_files("arch", files)
    assert matches[0] == "backend/architecture.md"
    assert "docs/old-architecture.md" in matches


def test_resolve_workspace_root_prefers_cli_cwd(tmp_path: Path) -> None:
    cfg = default_config()
    resolved = resolve_workspace_root(str(tmp_path), cfg)
    assert resolved == tmp_path.resolve()
