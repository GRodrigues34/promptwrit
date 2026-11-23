"""Qt modal dialogs for Workspace selection, Tag editing, and Settings."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from promptwrit.highlighter import PromptXmlHighlighter
from promptwrit.parser import expand_tag_snippet
from promptwrit.schema import AppConfig, TagDef


class WorkspaceDialog(QDialog):
    """Dialog to choose or browse for the active workspace root."""

    def __init__(self, current_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Workspace Root")
        self.setMinimumWidth(520)
        self.selected_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        layout.addWidget(QLabel("Workspace directory (used for #file path autocomplete):"))

        row = QHBoxLayout()
        self.path_input = QLineEdit(str(current_root))
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        row.addWidget(self.path_input, 1)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("primaryBtn")
        apply_btn.clicked.connect(self._apply)
        actions.addWidget(cancel_btn)
        actions.addWidget(apply_btn)
        layout.addLayout(actions)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select Workspace", self.path_input.text())
        if chosen:
            self.path_input.setText(chosen)

    def _apply(self) -> None:
        candidate = Path(self.path_input.text().strip()).expanduser().resolve()
        if candidate.exists() and candidate.is_dir():
            self.selected_path = candidate
            self.accept()
        else:
            QMessageBox.warning(self, "Invalid Directory", "The selected directory does not exist.")


class TagEditorDialog(QDialog):
    """Dialog to create or edit a Main or Complementary tag and its template."""

    def __init__(self, existing: TagDef | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Tag" if existing else "New Tag")
        self.setMinimumWidth(480)
        self.result_tag: TagDef | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 18, 18, 18)

        layout.addWidget(QLabel("Tag Name (uppercase):"))
        self.name_input = QLineEdit(existing.name if existing else "")
        self.name_input.setPlaceholderText("e.g. PERF")
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Kind:"))
        self.kind_combo = QComboBox()
        self.kind_combo.addItem("Complementary (allowed anywhere)", "complementary")
        self.kind_combo.addItem("Main (root wrapper, auto-pluralizes)", "main")
        if existing and existing.kind == "main":
            self.kind_combo.setCurrentIndex(1)
        layout.addWidget(self.kind_combo)

        layout.addWidget(QLabel("Plural Name (Main tags only):"))
        self.plural_input = QLineEdit(existing.plural if existing else "")
        self.plural_input.setPlaceholderText("e.g. PERFS")
        layout.addWidget(self.plural_input)

        layout.addWidget(QLabel("Description / Canonical Ghost Hint:"))
        self.desc_input = QLineEdit(existing.description if existing else "")
        self.desc_input.setPlaceholderText("Short guidance shown in -- Tags: and placeholder")
        layout.addWidget(self.desc_input)

        layout.addWidget(QLabel("Template Child Tags (comma-separated, optional):"))
        self.tmpl_input = QLineEdit(", ".join(existing.template) if existing else "")
        self.tmpl_input.setPlaceholderText("OBJECTIVE, CONTEXT, CONSTRAINTS")
        layout.addWidget(self.tmpl_input)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Tag")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        layout.addLayout(actions)

    def _save(self) -> None:
        name = self.name_input.text().strip().upper()
        desc = self.desc_input.text().strip()
        kind = self.kind_combo.currentData()
        plural = self.plural_input.text().strip().upper()
        tmpl = [p.strip().upper() for p in self.tmpl_input.text().split(",") if p.strip()]

        if not name or not re.fullmatch(r"[A-Z_][A-Z0-9_-]*", name):
            QMessageBox.warning(self, "Invalid Name", "Use uppercase letters, digits, or underscores.")
            return
        if not desc:
            QMessageBox.warning(self, "Missing Description", "A short description is required.")
            return

        self.result_tag = TagDef(
            name=name,
            kind="main" if kind == "main" else "complementary",
            plural=plural,
            description=desc,
            template=tmpl,
        )
        self.accept()


class _TemplateCodeEdit(QPlainTextEdit):
    """Restricted XML template editor: only allows adding (< autocomplete) or removing child tags."""

    def __init__(self, dialog: TemplateEditorDialog) -> None:
        super().__init__()
        self._dlg = dialog
        self.setObjectName("promptEditor")

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        key = event.key()
        mods = event.modifiers()

        if self._dlg.is_autocomplete_visible():
            if key == Qt.Key.Key_Down:
                self._dlg.move_autocomplete(1)
                return
            if key == Qt.Key.Key_Up:
                self._dlg.move_autocomplete(-1)
                return
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._dlg.accept_autocomplete()
                return
            if key == Qt.Key.Key_Escape:
                self._dlg.hide_autocomplete()
                return

        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End):
            super().keyPressEvent(event)
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not mods:
            self._dlg.insert_blank_child_line()
            return

        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._dlg.handle_delete_key(is_backspace=(key == Qt.Key.Key_Backspace))
            return

        ch = event.text()
        if ch and not (mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            if ch == "<" or (self._dlg.is_typing_tag_prefix() and re.fullmatch(r"[A-Za-z0-9_-]", ch)):
                self._dlg.insert_tag_filter_char(ch)
            return

        if key == Qt.Key.Key_Escape:
            self._dlg.reject()


class TemplateEditorDialog(QDialog):
    """Modal to view and edit child tags of a template using `<` autocomplete only."""

    def __init__(self, tag: TagDef, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tag = tag
        self.config = config
        self.setWindowTitle(f"Edit Template: <{tag.name}>")
        self.setMinimumSize(640, 360)
        self.updated_template: list[str] | None = None
        self._suppress = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(
            QLabel(
                f"Type '<' inside <{tag.name}> to add a tag, Enter for a new line, or Backspace/Delete to remove a tag:"
            )
        )

        temp_cfg = AppConfig(
            templates_enabled=True,
            indent_spaces=config.indent_spaces,
            tags=config.tags,
        )
        preview_text, _ = expand_tag_snippet(tag, temp_cfg)

        self.editor = _TemplateCodeEdit(self)
        hints = {t.description for t in config.tags if t.description}
        self.highlighter = PromptXmlHighlighter(self.editor.document(), known_hints=hints)
        self.editor.setPlainText(preview_text)
        layout.addWidget(self.editor, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Template")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        layout.addLayout(actions)

        self.popup = QListWidget(self)
        self.popup.setObjectName("autocompletePopup")
        self.popup.setWindowFlags(Qt.WindowType.SubWindow)
        self.popup.hide()
        self.popup.itemClicked.connect(lambda _item: self.accept_autocomplete())

        # Start cursor on the first child line.
        cur = self.editor.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.Start)
        cur.movePosition(QTextCursor.MoveOperation.Down)
        self.editor.setTextCursor(cur)

    def _line_bounds(self) -> tuple[int, int, int]:
        """Return (block_index, total_blocks, line_start_pos) for current cursor."""
        cur = self.editor.textCursor()
        block = cur.block()
        return block.blockNumber(), self.editor.document().blockCount(), block.position()

    def is_typing_tag_prefix(self) -> bool:
        cur = self.editor.textCursor()
        block = cur.block()
        idx = cur.blockNumber()
        total = self.editor.document().blockCount()
        if idx == 0 or idx >= total - 1:
            return False
        before = block.text()[: cur.positionInBlock()]
        return bool(re.search(r"^\s*<[A-Za-z0-9_-]*$", before))

    def is_autocomplete_visible(self) -> bool:
        return self.popup.isVisible()

    def hide_autocomplete(self) -> None:
        self.popup.hide()
        self.popup.clear()

    def move_autocomplete(self, delta: int) -> None:
        count = self.popup.count()
        if count == 0:
            return
        row = self.popup.currentRow()
        self.popup.setCurrentRow((row + delta) % count if row >= 0 else 0)

    def _current_children(self) -> list[str]:
        raw = self.editor.toPlainText()
        outer = re.match(
            rf"^<{re.escape(self.tag.name)}>\s*(.*?)\s*</{re.escape(self.tag.name)}>$",
            raw.strip(),
            re.DOTALL | re.IGNORECASE,
        )
        body = outer.group(1) if outer else raw
        return [
            m.group(1).upper()
            for m in re.finditer(r"^\s*<\s*([A-Za-z_][A-Za-z0-9_-]*)\s*>", body, re.MULTILINE)
            if m.group(1).upper() != self.tag.name
        ]

    def _position_popup(self) -> None:
        rect = self.editor.cursorRect()
        pt = self.editor.mapTo(self, rect.bottomLeft() + QPoint(0, 4))
        popup_w = min(480, max(320, self.width() - 48))
        popup_h = min(190, 28 * max(1, self.popup.count()) + 10)
        x = min(pt.x(), max(16, self.width() - popup_w - 16))
        y = pt.y()
        if y + popup_h > self.height() - 40:
            y = max(16, self.editor.mapTo(self, rect.topLeft() - QPoint(0, popup_h + 4)).y())
        self.popup.setGeometry(x, y, popup_w, popup_h)
        self.popup.raise_()

    def _refresh_popup(self, query: str) -> None:
        existing = set(self._current_children())
        q = query.upper()
        candidates = [
            t
            for t in self.config.complementary_tags()
            if t.name not in existing and (not q or t.name.startswith(q))
        ]
        self.popup.clear()
        if not candidates:
            self.hide_autocomplete()
            return
        for tag in candidates:
            item = QListWidgetItem(f"{tag.name:<13} | {tag.description}")
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self.popup.addItem(item)
        self.popup.setCurrentRow(0)
        self._position_popup()
        self.popup.show()

    def insert_tag_filter_char(self, ch: str) -> None:
        idx, total, _ = self._line_bounds()
        if idx == 0 or idx >= total - 1:
            return
        cur = self.editor.textCursor()
        line_text = cur.block().text()
        if ch == "<":
            if line_text.strip() != "":
                return
            indent = " " * max(1, self.config.indent_spaces)
            cur.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cur.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            cur.insertText(f"{indent}<")
            self.editor.setTextCursor(cur)
            self._refresh_popup("")
            return

        cur.insertText(ch)
        self.editor.setTextCursor(cur)
        before = cur.block().text()[: cur.positionInBlock()]
        m = re.search(r"<([A-Za-z0-9_-]*)$", before)
        if m:
            self._refresh_popup(m.group(1))

    def accept_autocomplete(self) -> None:
        item = self.popup.currentItem()
        if item is None:
            self.hide_autocomplete()
            return
        tag_def: TagDef = item.data(Qt.ItemDataRole.UserRole)
        self.hide_autocomplete()
        indent = " " * max(1, self.config.indent_spaces)
        cur = self.editor.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cur.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cur.insertText(f"{indent}<{tag_def.name}>{tag_def.description}</{tag_def.name}>")
        self.editor.setTextCursor(cur)

    def insert_blank_child_line(self) -> None:
        idx, total, _ = self._line_bounds()
        if idx >= total - 1:
            return
        cur = self.editor.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        indent = " " * max(1, self.config.indent_spaces)
        cur.insertText(f"\n{indent}")
        self.editor.setTextCursor(cur)

    def handle_delete_key(self, is_backspace: bool) -> None:
        idx, total, _ = self._line_bounds()
        if idx == 0 or idx >= total - 1:
            return
        cur = self.editor.textCursor()
        line_text = cur.block().text()
        # If typing `<prefix`, allow deleting characters of the prefix.
        if is_backspace and re.fullmatch(r"\s*<[A-Za-z0-9_-]+", line_text):
            cur.deletePreviousChar()
            self.editor.setTextCursor(cur)
            m = re.search(r"<([A-Za-z0-9_-]*)$", cur.block().text())
            self._refresh_popup(m.group(1) if m else "")
            return
        if is_backspace and re.fullmatch(r"\s*<", line_text):
            self.hide_autocomplete()
            cur.deletePreviousChar()
            self.editor.setTextCursor(cur)
            return

        # Otherwise remove the entire child tag line cleanly.
        self.hide_autocomplete()
        lines = self.editor.toPlainText().splitlines()
        if 0 < idx < len(lines) - 1:
            del lines[idx]
            self.editor.setPlainText("\n".join(lines))
            new_cur = self.editor.textCursor()
            new_cur.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(min(idx, len(lines) - 1)):
                new_cur.movePosition(QTextCursor.MoveOperation.Down)
            self.editor.setTextCursor(new_cur)

    def _save(self) -> None:
        seen: set[str] = set()
        cleaned: list[str] = []
        for child in self._current_children():
            if child not in seen:
                seen.add(child)
                cleaned.append(child)
        self.updated_template = cleaned
        self.accept()


class SettingsDialog(QDialog):
    """Settings modal for Templates toggle, indexing, copy behavior, and tag management."""

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PromptWrit Settings")
        self.setMinimumSize(640, 560)

        self.draft = AppConfig(
            templates_enabled=config.templates_enabled,
            strip_empty_tags=config.strip_empty_tags,
            respect_gitignore=config.respect_gitignore,
            extra_ignores=list(config.extra_ignores),
            indent_spaces=config.indent_spaces,
            after_copy=config.after_copy,
            theme=config.theme,
            last_workspace=config.last_workspace,
            pinned_workspace=config.pinned_workspace,
            tags=[
                TagDef(
                    name=t.name,
                    kind=t.kind,
                    plural=t.plural,
                    description=t.description,
                    template=list(t.template),
                )
                for t in config.tags
            ],
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self.chk_templates = QCheckBox("Templates (expand assigned child tags on Tab)")
        self.chk_templates.setChecked(self.draft.templates_enabled)
        layout.addWidget(self.chk_templates)

        self.chk_strip = QCheckBox("Strip empty tags on copy")
        self.chk_strip.setChecked(self.draft.strip_empty_tags)
        layout.addWidget(self.chk_strip)

        self.chk_gitignore = QCheckBox("Respect .gitignore when indexing #files")
        self.chk_gitignore.setChecked(self.draft.respect_gitignore)
        layout.addWidget(self.chk_gitignore)

        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel("After copy:"))
        self.combo_after = QComboBox()
        self.combo_after.addItem("Copy & Close", "close")
        self.combo_after.addItem("Copy & Stay Open", "stay")
        self.combo_after.setCurrentIndex(1 if self.draft.after_copy == "stay" else 0)
        opts_row.addWidget(self.combo_after)

        opts_row.addSpacing(16)
        opts_row.addWidget(QLabel("Indent:"))
        self.combo_indent = QComboBox()
        self.combo_indent.addItem("2 spaces", 2)
        self.combo_indent.addItem("4 spaces", 4)
        self.combo_indent.setCurrentIndex(1 if self.draft.indent_spaces == 4 else 0)
        opts_row.addWidget(self.combo_indent)
        opts_row.addStretch(1)
        layout.addLayout(opts_row)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # Tab 1: Main Tags & Complementary Tags
        tags_tab = QWidget()
        tags_layout = QVBoxLayout(tags_tab)
        tags_layout.setContentsMargins(4, 4, 4, 4)
        tags_layout.setSpacing(6)

        main_hdr = QLabel("Main Tags")
        main_hdr.setObjectName("sectionHeader")
        tags_layout.addWidget(main_hdr)
        self.main_list = QListWidget()
        self.main_list.itemClicked.connect(lambda _i: self.comp_list.clearSelection())
        self.main_list.itemDoubleClicked.connect(lambda _i: self._edit_tag())
        tags_layout.addWidget(self.main_list, 1)

        comp_hdr = QLabel("Complementary Tags")
        comp_hdr.setObjectName("sectionHeader")
        tags_layout.addWidget(comp_hdr)
        self.comp_list = QListWidget()
        self.comp_list.itemClicked.connect(lambda _i: self.main_list.clearSelection())
        self.comp_list.itemDoubleClicked.connect(lambda _i: self._edit_tag())
        tags_layout.addWidget(self.comp_list, 1)

        tag_btns = QHBoxLayout()
        new_btn = QPushButton("+ New Tag")
        new_btn.clicked.connect(self._new_tag)
        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self._edit_tag)
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._delete_tag)
        tag_btns.addWidget(new_btn)
        tag_btns.addWidget(edit_btn)
        tag_btns.addWidget(del_btn)
        tag_btns.addStretch(1)
        tags_layout.addLayout(tag_btns)
        self.tabs.addTab(tags_tab, "Tags")

        # Tab 2: Templates (Tag Name + Eye preview button)
        tmpl_tab = QWidget()
        tmpl_outer = QVBoxLayout(tmpl_tab)
        tmpl_outer.setContentsMargins(4, 4, 4, 4)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.tmpl_container = QWidget()
        self.tmpl_layout = QVBoxLayout(self.tmpl_container)
        self.tmpl_layout.setContentsMargins(4, 4, 4, 4)
        self.tmpl_layout.setSpacing(6)
        scroll.setWidget(self.tmpl_container)
        tmpl_outer.addWidget(scroll)
        self.tabs.addTab(tmpl_tab, "Templates")

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        layout.addLayout(actions)

        self._refresh_tag_list()

    def _refresh_tag_list(self) -> None:
        self.main_list.clear()
        self.comp_list.clear()
        for tag in self.draft.tags:
            item = QListWidgetItem(f"{tag.name} - {tag.description}")
            item.setData(Qt.ItemDataRole.UserRole, tag.name)
            if tag.kind == "main":
                self.main_list.addItem(item)
            else:
                self.comp_list.addItem(item)

        while self.tmpl_layout.count():
            child = self.tmpl_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        bold_font = QFont()
        bold_font.setBold(True)
        for tag in self.draft.tags:
            if not tag.template:
                continue
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(6, 4, 6, 4)
            lbl = QLabel(tag.name)
            lbl.setFont(bold_font)
            eye_btn = QPushButton("👁")
            eye_btn.setToolTip(f"Preview <{tag.name}> template")
            eye_btn.setFixedWidth(40)
            eye_btn.clicked.connect(lambda _checked=False, t=tag: self._preview_template(t))
            row.addWidget(lbl)
            row.addStretch(1)
            row.addWidget(eye_btn)
            self.tmpl_layout.addWidget(row_widget)
        self.tmpl_layout.addStretch(1)

    def _preview_template(self, tag: TagDef) -> None:
        dlg = TemplateEditorDialog(tag, self.draft, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.updated_template is not None:
            tag.template = dlg.updated_template
            self._refresh_tag_list()

    def _selected_tag_name(self) -> str | None:
        for lst in (self.main_list, self.comp_list):
            item = lst.currentItem()
            if item and item.isSelected():
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _new_tag(self) -> None:
        dlg = TagEditorDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_tag:
            self.draft.tags = [t for t in self.draft.tags if t.name != dlg.result_tag.name]
            self.draft.tags.append(dlg.result_tag)
            self._refresh_tag_list()

    def _edit_tag(self) -> None:
        name = self._selected_tag_name()
        if not name:
            return
        existing = self.draft.tag_map().get(name)
        if not existing:
            return
        dlg = TagEditorDialog(existing=existing, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_tag:
            self.draft.tags = [
                dlg.result_tag if t.name == existing.name else t for t in self.draft.tags
            ]
            self._refresh_tag_list()

    def _delete_tag(self) -> None:
        name = self._selected_tag_name()
        if not name:
            return
        self.draft.tags = [t for t in self.draft.tags if t.name != name]
        self._refresh_tag_list()

    def _save(self) -> None:
        self.draft.templates_enabled = self.chk_templates.isChecked()
        self.draft.strip_empty_tags = self.chk_strip.isChecked()
        self.draft.respect_gitignore = self.chk_gitignore.isChecked()
        self.draft.after_copy = self.combo_after.currentData()
        self.draft.indent_spaces = int(self.combo_indent.currentData())
        self.accept()
