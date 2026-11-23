"""End-to-end Textual pilot tests for PromptWritApp."""

import asyncio
from pathlib import Path

from promptwrit.app import PromptTextArea, PromptWritApp, SettingsScreen


def test_app_tag_autocomplete_and_legend_sync(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"

    async def _run() -> None:
        app = PromptWritApp(cli_cwd=str(tmp_path), config_file=cfg_file)
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.pause()
            editor = app.query_one("#prompt-editor", PromptTextArea)
            assert editor.has_focus

            await pilot.press("<", "f", "e", "a", "t")
            await pilot.pause()
            assert app.is_autocomplete_visible()

            await pilot.press("tab")
            await pilot.pause()
            assert not app.is_autocomplete_visible()
            assert "<FEATURE>" in editor.text
            assert "<OBJECTIVE>" in editor.text

            tags_text = str(app.query_one("#tags-content").render())
            assert "FEATURE:" in tags_text
            assert "OBJECTIVE:" in tags_text
            assert "FEATURES:" not in tags_text

    asyncio.run(_run())


def test_app_file_autocomplete_inserts_relative_path(tmp_path: Path) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "architecture.md").write_text("# Arch", encoding="utf-8")
    cfg_file = tmp_path / "config.json"

    async def _run() -> None:
        app = PromptWritApp(cli_cwd=str(tmp_path), config_file=cfg_file)
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.pause()
            editor = app.query_one("#prompt-editor", PromptTextArea)
            editor.text = "<CONTEXT></CONTEXT>"
            editor.cursor_location = (0, len("<CONTEXT>"))
            await pilot.pause()

            await pilot.press("#", "a", "r", "c", "h")
            await pilot.pause()
            assert app.is_autocomplete_visible()

            await pilot.press("tab")
            await pilot.pause()
            assert "backend/architecture.md" in editor.text

    asyncio.run(_run())


def test_app_settings_modal_opens_and_toggles_templates(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"

    async def _run() -> None:
        app = PromptWritApp(cli_cwd=str(tmp_path), config_file=cfg_file)
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.click("#settings-btn")
            await pilot.pause()
            assert isinstance(app.screen, SettingsScreen)

            await pilot.click("#sw-templates")
            await pilot.click("#set-save")
            await pilot.pause()
            assert app.config.templates_enabled is False

    asyncio.run(_run())
