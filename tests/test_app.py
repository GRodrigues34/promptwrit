"""Headless Qt tests for PromptWritWindow and dialogs."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from promptwrit.app import PromptWritWindow
from promptwrit.modals import SettingsDialog, TemplateEditorDialog


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_window_tag_autocomplete_and_legend_sync(tmp_path: Path) -> None:
    _ensure_qapp()
    cfg_file = tmp_path / "config.json"
    win = PromptWritWindow(cli_cwd=str(tmp_path), config_file=cfg_file)
    win.show()

    QTest.keyClicks(win.editor, "<feat")
    assert win.is_autocomplete_visible()

    QTest.keyClick(win.editor, Qt.Key.Key_Tab)
    assert not win.is_autocomplete_visible()
    assert "<FEATURE>" in win.editor.toPlainText()
    assert "<OBJECTIVE>" in win.editor.toPlainText()

    legend_text = win.tags_legend.toPlainText()
    assert "FEATURE:" in legend_text
    assert "OBJECTIVE:" in legend_text
    assert "FEATURES:" not in legend_text
    win.close()


def test_window_file_autocomplete_inserts_relative_path(tmp_path: Path) -> None:
    _ensure_qapp()
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "architecture.md").write_text("# Arch", encoding="utf-8")
    cfg_file = tmp_path / "config.json"

    win = PromptWritWindow(cli_cwd=str(tmp_path), config_file=cfg_file)
    win.show()
    win.editor.setPlainText("<CONTEXT></CONTEXT>")
    cursor = win.editor.textCursor()
    cursor.setPosition(len("<CONTEXT>"))
    win.editor.setTextCursor(cursor)

    QTest.keyClicks(win.editor, "#arch")
    assert win.is_autocomplete_visible()

    QTest.keyClick(win.editor, Qt.Key.Key_Tab)
    assert "backend/architecture.md" in win.editor.toPlainText()
    win.close()


def test_settings_dialog_toggles_templates(tmp_path: Path) -> None:
    _ensure_qapp()
    cfg_file = tmp_path / "config.json"
    win = PromptWritWindow(cli_cwd=str(tmp_path), config_file=cfg_file)

    dlg = SettingsDialog(win.config, parent=win)
    assert dlg.main_list.count() == len(win.config.main_tags())
    assert dlg.comp_list.count() == len(win.config.complementary_tags())
    assert dlg.tabs.count() == 2
    assert dlg.chk_templates.isChecked() is True
    dlg.chk_templates.setChecked(False)
    dlg._save()
    assert dlg.draft.templates_enabled is False
    win.close()


def test_ghost_hint_is_non_editable_and_restores_when_empty(tmp_path: Path) -> None:
    _ensure_qapp()
    cfg_file = tmp_path / "config.json"
    win = PromptWritWindow(cli_cwd=str(tmp_path), config_file=cfg_file)
    win.show()

    QTest.keyClicks(win.editor, "<feat")
    QTest.keyClick(win.editor, Qt.Key.Key_Tab)
    assert "<OBJECTIVE>Exact outcome or goal expected</OBJECTIVE>" in win.editor.toPlainText()
    assert win.editor.textCursor().hasSelection() is False

    # Typing immediately clears the ghost hint and inserts user text.
    QTest.keyClicks(win.editor, "Build X")
    text = win.editor.toPlainText()
    assert "<OBJECTIVE>Build X</OBJECTIVE>" in text
    assert "Exact outcome or goal expected" not in text

    # Deleting user text and moving to next tab-stop restores the ghost hint.
    for _ in range(len("Build X")):
        QTest.keyClick(win.editor, Qt.Key.Key_Backspace)
    QTest.keyClick(win.editor, Qt.Key.Key_Tab)
    assert "<OBJECTIVE>Exact outcome or goal expected</OBJECTIVE>" in win.editor.toPlainText()
    win.close()


def test_template_editor_dialog_saves_updated_children(tmp_path: Path) -> None:
    _ensure_qapp()
    cfg_file = tmp_path / "config.json"
    win = PromptWritWindow(cli_cwd=str(tmp_path), config_file=cfg_file)
    feature = win.config.tag_map()["FEATURE"]

    dlg = TemplateEditorDialog(feature, win.config, parent=win)
    dlg.show()

    # Arbitrary prose is blocked on existing tag lines.
    before = dlg.editor.toPlainText()
    QTest.keyClicks(dlg.editor, "hello")
    assert dlg.editor.toPlainText() == before

    # Delete removes the current child tag line (OBJECTIVE).
    QTest.keyClick(dlg.editor, Qt.Key.Key_Delete)
    assert "<OBJECTIVE>" not in dlg.editor.toPlainText()

    # Press Enter at end of line to add a new line, type <out and Tab to add OUTPUT.
    QTest.keyClick(dlg.editor, Qt.Key.Key_Return)
    QTest.keyClicks(dlg.editor, "<out")
    assert dlg.is_autocomplete_visible()
    QTest.keyClick(dlg.editor, Qt.Key.Key_Tab)
    assert "<OUTPUT>" in dlg.editor.toPlainText()

    dlg._save()
    assert "OBJECTIVE" not in (dlg.updated_template or [])
    assert "OUTPUT" in (dlg.updated_template or [])
    dlg.close()
    win.close()
