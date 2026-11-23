"""Qt modal dialogs for Workspace selection, Tag editing, and Settings."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
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


class TemplateEditorDialog(QDialog):
    """Modal to view and edit the expanded XML template for a tag."""

    def __init__(self, tag: TagDef, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tag = tag
        self.setWindowTitle(f"Edit Template: <{tag.name}>")
        self.setMinimumSize(620, 340)
        self.updated_template: list[str] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(
            QLabel(f"Edit child tags inside <{tag.name}>...</{tag.name}> (one child tag per line):")
        )

        temp_cfg = AppConfig(
            templates_enabled=True,
            indent_spaces=config.indent_spaces,
            tags=config.tags,
        )
        preview_text, _ = expand_tag_snippet(tag, temp_cfg)

        self.editor = QPlainTextEdit(preview_text)
        self.editor.setObjectName("promptEditor")
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

    def _save(self) -> None:
        raw = self.editor.toPlainText().strip()
        outer = re.match(
            rf"^<{re.escape(self.tag.name)}>\s*(.*?)\s*</{re.escape(self.tag.name)}>$",
            raw,
            re.DOTALL | re.IGNORECASE,
        )
        body = outer.group(1) if outer else raw
        children = [
            m.group(1).upper()
            for m in re.finditer(r"<\s*([A-Za-z_][A-Za-z0-9_-]*)\s*>", body)
        ]
        # Deduplicate while preserving order, excluding the wrapper tag itself.
        seen: set[str] = set()
        cleaned: list[str] = []
        for child in children:
            if child != self.tag.name and child not in seen:
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
