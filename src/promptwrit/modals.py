"""Qt modal dialogs for Workspace selection, Tag editing, and Settings."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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


class SettingsDialog(QDialog):
    """Settings modal for Templates toggle, indexing, copy behavior, and tag management."""

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PromptWrit Settings")
        self.setMinimumSize(620, 520)

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

        layout.addWidget(QLabel("Tags & Templates (double-click a row to edit):"))
        self.tag_table = QTableWidget(0, 4)
        self.tag_table.setHorizontalHeaderLabels(["Tag", "Type", "Description", "Template"])
        self.tag_table.setAlternatingRowColors(True)
        self.tag_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tag_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tag_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tag_table.verticalHeader().setVisible(False)
        self.tag_table.setShowGrid(False)
        self.tag_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header = self.tag_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tag_table.itemDoubleClicked.connect(lambda _item: self._edit_tag())
        layout.addWidget(self.tag_table, 1)

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
        layout.addLayout(tag_btns)

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
        self.tag_table.setRowCount(0)
        bold_font = QFont()
        bold_font.setBold(True)

        for row_idx, tag in enumerate(self.draft.tags):
            self.tag_table.insertRow(row_idx)
            name_item = QTableWidgetItem(tag.name)
            name_item.setFont(bold_font)
            name_item.setData(Qt.ItemDataRole.UserRole, tag.name)

            is_main = tag.kind == "main"
            kind_item = QTableWidgetItem("Main" if is_main else "Comp")
            kind_item.setForeground(QColor("#7eb2d6" if is_main else "#8fbcbb"))
            kind_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            desc_item = QTableWidgetItem(tag.description)
            desc_item.setToolTip(tag.description)

            tmpl_text = ", ".join(tag.template) if tag.template else "-"
            tmpl_item = QTableWidgetItem(tmpl_text)
            tmpl_item.setForeground(QColor("#8b98ab"))
            tmpl_item.setToolTip(tmpl_text)

            self.tag_table.setItem(row_idx, 0, name_item)
            self.tag_table.setItem(row_idx, 1, kind_item)
            self.tag_table.setItem(row_idx, 2, desc_item)
            self.tag_table.setItem(row_idx, 3, tmpl_item)

    def _selected_tag_name(self) -> str | None:
        row = self.tag_table.currentRow()
        if row < 0:
            return None
        item = self.tag_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

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
