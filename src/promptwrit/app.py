"""Standalone modern PySide6 desktop window for PromptWrit."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from promptwrit.clipboard import copy_to_clipboard
from promptwrit.highlighter import PromptXmlHighlighter
from promptwrit.indexer import fuzzy_match_files, list_workspace_files, resolve_workspace_root
from promptwrit.modals import SettingsDialog, WorkspaceDialog
from promptwrit.parser import (
    allowed_tags_for_context,
    apply_auto_pluralization,
    clean_prompt_for_copy,
    expand_tag_snippet,
    extract_active_tags,
    get_tag_stack_at_cursor,
)
from promptwrit.schema import AppConfig, TagDef, load_config, save_config
from promptwrit.styles import DARK_SLATE_QSS


@dataclass
class ActiveTrigger:
    """Active `<` tag or `#` file autocomplete trigger."""

    kind: str  # "tag" | "file"
    query: str
    start_index: int
    end_index: int


class PromptEditor(QPlainTextEdit):
    """Code-editor-like prompt input with Tab-stop and autocomplete key routing."""

    def __init__(self, window: PromptWritWindow) -> None:
        super().__init__()
        self._window = window
        self.setObjectName("promptEditor")
        self.setTabStopDistance(24)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        key = event.key()
        mods = event.modifiers()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (mods & Qt.KeyboardModifier.ControlModifier):
            self._window.copy_and_finish()
            return

        if self._window.is_autocomplete_visible():
            if key == Qt.Key.Key_Down:
                self._window.move_autocomplete(1)
                return
            if key == Qt.Key.Key_Up:
                self._window.move_autocomplete(-1)
                return
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._window.accept_autocomplete()
                return
            if key == Qt.Key.Key_Escape:
                self._window.hide_autocomplete()
                return

        if key == Qt.Key.Key_Tab and not (mods & Qt.KeyboardModifier.ShiftModifier):
            if self._window.jump_next_tab_stop():
                return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not mods:
            if self._window.handle_auto_indent_enter():
                return

        if key == Qt.Key.Key_Escape:
            self._window.close()
            return

        # Non-editable ghost hint handling
        ghost = self._window.ghost_hint_at_cursor()
        if ghost is not None:
            g_start, g_end, _hint = ghost
            if key == Qt.Key.Key_Delete:
                self._window.clear_ghost_hint(g_start, g_end)
                return
            if key == Qt.Key.Key_Right and not (mods & Qt.KeyboardModifier.ShiftModifier):
                cur = self.textCursor()
                cur.setPosition(g_end)
                self.setTextCursor(cur)
                return
            if event.text() and not (mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
                if key not in (Qt.Key.Key_Backspace, Qt.Key.Key_Escape):
                    self._window.clear_ghost_hint(g_start, g_end)

        super().keyPressEvent(event)


class PromptWritWindow(QMainWindow):
    """Independent modern dark-slate desktop window for PromptWrit."""

    def __init__(self, cli_cwd: str | None = None, config_file: Path | None = None) -> None:
        super().__init__()
        self.config_file = config_file
        self.config: AppConfig = load_config(config_file)
        self.workspace_root = resolve_workspace_root(cli_cwd, self.config)
        self.workspace_files: list[str] = []
        self._active_trigger: ActiveTrigger | None = None
        self._suppress_change = False

        self.setWindowTitle("PromptWrit")
        self.resize(900, 620)
        self.setStyleSheet(DARK_SLATE_QSS)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 16, 18, 14)
        root_layout.setSpacing(10)

        # Header bar
        header = QHBoxLayout()
        title = QLabel("PromptWrit")
        title.setObjectName("headerTitle")
        self.workspace_btn = QPushButton(f"📁  {self.workspace_root.name}")
        self.workspace_btn.setObjectName("workspaceBtn")
        self.workspace_btn.clicked.connect(self.open_workspace_dialog)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setToolTip("Settings (Ctrl+S)")
        self.settings_btn.clicked.connect(self.open_settings_dialog)

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.workspace_btn)
        header.addWidget(self.settings_btn)
        root_layout.addLayout(header)

        # Top read-only -- Tags: box
        tags_group = QGroupBox("-- Tags:")
        tags_layout = QVBoxLayout(tags_group)
        tags_layout.setContentsMargins(6, 4, 6, 4)
        self.tags_legend = QPlainTextEdit()
        self.tags_legend.setObjectName("tagsLegend")
        self.tags_legend.setReadOnly(True)
        self.tags_legend.setMaximumHeight(140)
        self.tags_legend.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tags_layout.addWidget(self.tags_legend)
        root_layout.addWidget(tags_group)

        # Bottom editable -- Prompt: box
        prompt_group = QGroupBox("-- Prompt:")
        prompt_group.setObjectName("promptGroup")
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_layout.setContentsMargins(6, 4, 6, 4)
        self.editor = PromptEditor(self)
        self.highlighter = PromptXmlHighlighter(
            self.editor.document(),
            known_hints=self._known_hints(),
        )
        self.editor.textChanged.connect(self._on_editor_changed)
        self.editor.cursorPositionChanged.connect(self._on_cursor_moved)
        prompt_layout.addWidget(self.editor)
        root_layout.addWidget(prompt_group, 1)

        # Footer bar
        self.footer = QLabel(
            "Tab: Accept / Next Slot   •   #: File Path   •   Ctrl+Enter: Copy & Close   •   Esc: Cancel"
        )
        self.footer.setObjectName("footerBar")
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(self.footer)

        # Floating IDE-style autocomplete popup anchored to central widget
        self.popup = QListWidget(self)
        self.popup.setObjectName("autocompletePopup")
        self.popup.setWindowFlags(Qt.WindowType.SubWindow)
        self.popup.hide()
        self.popup.itemClicked.connect(lambda _item: self.accept_autocomplete())
        self.installEventFilter(self)

        self._reindex_workspace()
        self._refresh_tags_legend()
        self.editor.setFocus()

    def _known_hints(self) -> set[str]:
        return {t.description for t in self.config.tags if t.description}

    def _reindex_workspace(self) -> None:
        self.workspace_files = list_workspace_files(
            self.workspace_root,
            respect_gitignore=self.config.respect_gitignore,
            extra_ignores=self.config.extra_ignores,
        )
        self.workspace_btn.setText(f"📁  {self.workspace_root.name}")

    def _refresh_tags_legend(self) -> None:
        active = extract_active_tags(self.editor.toPlainText(), self.config)
        if not active:
            self.tags_legend.setPlainText("")
            return
        self.tags_legend.setPlainText("\n".join(f"{name}: {desc}" for name, desc in active))
        bar = self.tags_legend.verticalScrollBar()
        bar.setValue(bar.maximum())

    def is_autocomplete_visible(self) -> bool:
        return self.popup.isVisible()

    def hide_autocomplete(self) -> None:
        self.popup.hide()
        self.popup.clear()
        self._active_trigger = None

    def move_autocomplete(self, delta: int) -> None:
        count = self.popup.count()
        if count == 0:
            return
        row = self.popup.currentRow()
        next_row = (row + delta) % count if row >= 0 else 0
        self.popup.setCurrentRow(next_row)

    def _detect_trigger(self, text: str, cursor_idx: int) -> ActiveTrigger | None:
        before = text[:cursor_idx]
        tag_match = re.search(r"<([A-Za-z0-9_-]*)$", before)
        if tag_match:
            return ActiveTrigger("tag", tag_match.group(1), tag_match.start(), cursor_idx)
        file_match = re.search(r"#([^\s<>#]*)$", before)
        if file_match:
            return ActiveTrigger("file", file_match.group(1), file_match.start(), cursor_idx)
        return None

    def _position_popup_at_cursor(self) -> None:
        cursor_rect = self.editor.cursorRect()
        local_pt = cursor_rect.bottomLeft() + QPoint(0, 4)
        win_pt = self.editor.mapTo(self, local_pt)

        popup_w = min(560, max(360, self.width() - 60))
        row_h = max(26, self.popup.sizeHintForRow(0) if self.popup.count() else 28)
        popup_h = min(230, row_h * self.popup.count() + 12)

        x = min(win_pt.x(), max(16, self.width() - popup_w - 20))
        y = win_pt.y()
        if y + popup_h > self.height() - 36:
            above_pt = self.editor.mapTo(self, cursor_rect.topLeft() - QPoint(0, popup_h + 4))
            y = max(16, above_pt.y())

        self.popup.setGeometry(x, y, popup_w, popup_h)
        self.popup.raise_()

    def _update_autocomplete(self) -> None:
        text = self.editor.toPlainText()
        cursor_idx = self.editor.textCursor().position()
        trigger = self._detect_trigger(text, cursor_idx)
        if trigger is None:
            self.hide_autocomplete()
            return

        self.popup.clear()
        if trigger.kind == "tag":
            stack = get_tag_stack_at_cursor(text, trigger.start_index)
            candidates = allowed_tags_for_context(stack, self.config)
            q = trigger.query.upper()
            matched = [t for t in candidates if t.name.startswith(q)] if q else candidates
            if not matched:
                self.hide_autocomplete()
                return
            for tag in matched:
                item = QListWidgetItem(f"{tag.name:<13} | {tag.description}")
                item.setData(Qt.ItemDataRole.UserRole, ("tag", tag))
                self.popup.addItem(item)
        else:
            matched_files = fuzzy_match_files(trigger.query, self.workspace_files, limit=10)
            if not matched_files:
                self.hide_autocomplete()
                return
            for idx, rel in enumerate(matched_files, start=1):
                item = QListWidgetItem(f"{idx}. {rel}")
                item.setData(Qt.ItemDataRole.UserRole, ("file", rel))
                self.popup.addItem(item)

        self._active_trigger = trigger
        self.popup.setCurrentRow(0)
        self._position_popup_at_cursor()
        self.popup.show()

    def accept_autocomplete(self) -> None:
        item = self.popup.currentItem()
        trigger = self._active_trigger
        if item is None or trigger is None:
            self.hide_autocomplete()
            return

        kind, payload = item.data(Qt.ItemDataRole.UserRole)
        self.hide_autocomplete()
        text = self.editor.toPlainText()

        if kind == "file" and isinstance(payload, str):
            self._suppress_change = True
            cursor = self.editor.textCursor()
            cursor.setPosition(trigger.start_index)
            cursor.setPosition(trigger.end_index, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(payload)
            self.editor.setTextCursor(cursor)
            self._suppress_change = False
            self._refresh_tags_legend()
            return

        if kind == "tag" and isinstance(payload, TagDef):
            line_start = text.rfind("\n", 0, trigger.start_index) + 1
            stack = get_tag_stack_at_cursor(text, trigger.start_index)
            expected_indent = " " * (len(stack) * max(1, self.config.indent_spaces))
            leading = text[line_start : trigger.start_index]
            replace_start = line_start if leading.strip() == "" else trigger.start_index
            base_indent = expected_indent if leading.strip() == "" else " " * (trigger.start_index - line_start)

            snippet, stops = expand_tag_snippet(payload, self.config, base_indent=base_indent)
            if leading.strip() == "":
                snippet = f"{expected_indent}{snippet}"

            new_text = text[:replace_start] + snippet + text[trigger.end_index :]
            pluralized = apply_auto_pluralization(new_text, self.config)

            self._suppress_change = True
            self.editor.setPlainText(pluralized)
            self._suppress_change = False

            if stops and stops[0].hint:
                hint = stops[0].hint
                idx = pluralized.find(hint, replace_start)
                if idx != -1:
                    self._set_cursor_pos(idx)

            self._refresh_tags_legend()

    def handle_auto_indent_enter(self) -> bool:
        """Insert a newline preserving indentation (and indenting inside open tags)."""
        if self.ghost_hint_at_cursor() is not None:
            return False
        text = self.editor.toPlainText()
        pos = self.editor.textCursor().position()
        line_start = text.rfind("\n", 0, pos) + 1
        line_before = text[line_start:pos]
        leading = re.match(r"^[ \t]*", line_before).group(0)
        indent_unit = " " * max(1, self.config.indent_spaces)
        if re.search(r"<[A-Za-z_][A-Za-z0-9_-]*>\s*$", line_before):
            leading += indent_unit
        self.editor.insertPlainText(f"\n{leading}")
        return True

    def _set_cursor_pos(self, pos: int) -> None:
        cursor = self.editor.textCursor()
        cursor.setPosition(pos)
        self.editor.setTextCursor(cursor)

    def ghost_hint_at_cursor(self) -> tuple[int, int, str] | None:
        """Return (start, end, hint) if cursor sits at/inside a canonical ghost hint."""
        text = self.editor.toPlainText()
        pos = self.editor.textCursor().position()
        tag_map = self.config.tag_map()

        for match in re.finditer(r"<([A-Za-z_][A-Za-z0-9_-]*)>([^<>]*)</\1>", text):
            name = match.group(1).upper()
            body = match.group(2)
            tag_def = tag_map.get(name)
            if tag_def and tag_def.description and body == tag_def.description:
                g_start, g_end = match.start(2), match.end(2)
                if g_start <= pos <= g_end:
                    return g_start, g_end, body
        return None

    def clear_ghost_hint(self, start: int, end: int) -> None:
        """Silently remove a ghost hint range and place cursor at start."""
        self._suppress_change = True
        cursor = self.editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        self.editor.setTextCursor(cursor)
        self._suppress_change = False

    def _on_cursor_moved(self) -> None:
        if self._suppress_change:
            return
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            return

        pos = cursor.position()
        # 1. Prevent cursor from resting inside a ghost hint: snap to its start.
        ghost = self.ghost_hint_at_cursor()
        if ghost is not None and pos > ghost[0]:
            self._suppress_change = True
            self._set_cursor_pos(ghost[0])
            self._suppress_change = False
            return

        # 2. Restore canonical ghost hint for any empty tag the cursor has left.
        text = self.editor.toPlainText()
        tag_map = self.config.tag_map()
        for match in re.finditer(r"<([A-Za-z_][A-Za-z0-9_-]*)></\1>", text):
            name = match.group(1).upper()
            tag_def = tag_map.get(name)
            if not tag_def or not tag_def.description:
                continue
            insert_at = match.end(1) + 1  # right after '>'
            if pos != insert_at:
                new_text = text[:insert_at] + tag_def.description + text[insert_at:]
                offset = len(tag_def.description) if pos > insert_at else 0
                self._suppress_change = True
                self.editor.setPlainText(new_text)
                self._set_cursor_pos(pos + offset)
                self._suppress_change = False
                break

    def _find_next_hint_pos(self, text: str, start_from: int) -> int | None:
        best_pos: int | None = None
        for tag in self.config.tags:
            if not tag.description:
                continue
            token = f">{tag.description}</"
            found = text.find(token, start_from)
            if found != -1:
                pos = found + 1
                if best_pos is None or pos < best_pos:
                    best_pos = pos
        return best_pos

    def _find_first_complementary_pos(self, text: str) -> int | None:
        comp_names = {t.name for t in self.config.complementary_tags()}
        best_pos: int | None = None
        for match in re.finditer(r"<([A-Za-z_][A-Za-z0-9_-]*)>", text):
            if match.group(1).upper() in comp_names:
                pos = match.end()
                if best_pos is None or pos < best_pos:
                    best_pos = pos
        return best_pos

    def jump_next_tab_stop(self) -> bool:
        """Jump cursor to the next ghost hint, wrapping to the first complementary tag."""
        text = self.editor.toPlainText()
        cursor = self.editor.textCursor()
        next_pos = self._find_next_hint_pos(text, cursor.position() + 1)
        if next_pos is None:
            next_pos = self._find_next_hint_pos(text, 0)
        if next_pos is None:
            next_pos = self._find_first_complementary_pos(text)

        if next_pos is not None:
            self._set_cursor_pos(next_pos)
            return True
        return False

    def _on_editor_changed(self) -> None:
        if self._suppress_change:
            return
        self._refresh_tags_legend()
        self._update_autocomplete()

    def open_workspace_dialog(self) -> None:
        dlg = WorkspaceDialog(self.workspace_root, parent=self)
        if dlg.exec() == WorkspaceDialog.DialogCode.Accepted and dlg.selected_path:
            self.workspace_root = dlg.selected_path
            self.config.last_workspace = str(dlg.selected_path)
            save_config(self.config, self.config_file)
            self._reindex_workspace()
        self.editor.setFocus()

    def open_settings_dialog(self) -> None:
        dlg = SettingsDialog(self.config, parent=self)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            self.config = dlg.draft
            save_config(self.config, self.config_file)
            self.highlighter.set_known_hints(self._known_hints())
            self._reindex_workspace()
            self._refresh_tags_legend()
        self.editor.setFocus()

    def copy_and_finish(self) -> None:
        cleaned = clean_prompt_for_copy(
            self.editor.toPlainText(),
            known_hints=self._known_hints(),
            strip_empty_tags=self.config.strip_empty_tags,
        )
        if not cleaned:
            self.footer.setText("Prompt is empty.")
            return
        if copy_to_clipboard(cleaned):
            if self.config.after_copy == "close":
                self.close()
            else:
                self.footer.setText("Copied prompt to clipboard!")
        else:
            self.footer.setText("Clipboard copy failed (wl-copy / xclip unavailable).")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt override)
        if watched is self and event.type() == QEvent.Type.Resize and self.popup.isVisible():
            self._position_popup_at_cursor()
        return super().eventFilter(watched, event)
