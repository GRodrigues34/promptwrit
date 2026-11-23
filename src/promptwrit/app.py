"""PromptWrit Textual TUI application."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Select, Static, Switch, TextArea
from textual.widgets.option_list import Option
from textual.widgets.text_area import Selection

from promptwrit.clipboard import copy_to_clipboard
from promptwrit.indexer import fuzzy_match_files, list_workspace_files, resolve_workspace_root
from promptwrit.parser import (
    allowed_tags_for_context,
    apply_auto_pluralization,
    clean_prompt_for_copy,
    expand_tag_snippet,
    extract_active_tags,
    get_tag_stack_at_cursor,
)
from promptwrit.schema import AppConfig, TagDef, load_config, save_config


@dataclass
class ActiveTrigger:
    """Represents an active `<` tag or `#` file autocomplete trigger."""

    kind: str  # "tag" | "file"
    query: str
    start_index: int
    end_index: int


def _row_col_to_index(text: str, row: int, col: int) -> int:
    """Convert TextArea (row, col) to flat character index."""
    lines = text.splitlines(keepends=True)
    if row >= len(lines):
        return len(text)
    return sum(len(lines[i]) for i in range(row)) + min(col, len(lines[row].rstrip("\r\n")))


def _index_to_row_col(text: str, index: int) -> tuple[int, int]:
    """Convert flat character index to TextArea (row, col)."""
    clamped = max(0, min(index, len(text)))
    prefix = text[:clamped]
    row = prefix.count("\n")
    last_nl = prefix.rfind("\n")
    col = clamped if last_nl == -1 else clamped - last_nl - 1
    return row, col


class PromptTextArea(TextArea):
    """TextArea that delegates Tab/Up/Down/Enter to PromptWrit when autocomplete is open."""

    async def _on_key(self, event: events.Key) -> None:
        app = self.app
        if isinstance(app, PromptWritApp) and app.is_autocomplete_visible():
            if event.key in ("down", "up", "tab", "enter", "escape"):
                event.prevent_default()
                event.stop()
                if event.key == "down":
                    app.move_autocomplete(1)
                elif event.key == "up":
                    app.move_autocomplete(-1)
                elif event.key in ("tab", "enter"):
                    app.accept_autocomplete()
                elif event.key == "escape":
                    app.hide_autocomplete()
                return

        if event.key == "tab" and isinstance(app, PromptWritApp):
            if app.jump_next_tab_stop():
                event.prevent_default()
                event.stop()
                return

        await super()._on_key(event)


class WorkspaceScreen(ModalScreen[Path | None]):
    """Modal to switch the active workspace directory."""

    def __init__(self, current_root: Path) -> None:
        super().__init__()
        self.current_root = current_root

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-box"):
            yield Label("Select Workspace Root", classes="modal-title")
            yield Input(value=str(self.current_root), id="workspace-input", placeholder="/path/to/repo")
            with Horizontal(classes="modal-actions"):
                yield Button("Cancel", id="ws-cancel")
                yield Button("Apply", variant="primary", id="ws-apply")

    @on(Button.Pressed, "#ws-cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#ws-apply")
    @on(Input.Submitted, "#workspace-input")
    def _apply(self) -> None:
        raw = self.query_one("#workspace-input", Input).value.strip()
        candidate = Path(raw).expanduser().resolve()
        if candidate.exists() and candidate.is_dir():
            self.dismiss(candidate)
        else:
            self.notify("Directory does not exist.", severity="error")


class TagEditorScreen(ModalScreen[TagDef | None]):
    """Modal to create or edit a single tag and its optional template."""

    def __init__(self, existing: TagDef | None = None) -> None:
        super().__init__()
        self.existing = existing

    def compose(self) -> ComposeResult:
        tag = self.existing
        with Vertical(classes="modal-box"):
            yield Label("Edit Tag" if tag else "New Tag", classes="modal-title")
            yield Label("Name (uppercase):")
            yield Input(value=tag.name if tag else "", id="tag-name", placeholder="e.g. PERF")
            yield Label("Kind:")
            yield Select(
                [("Main (root wrapper)", "main"), ("Complementary (nested)", "complementary")],
                value=tag.kind if tag else "complementary",
                id="tag-kind",
            )
            yield Label("Plural name (Main tags only):")
            yield Input(value=tag.plural if tag else "", id="tag-plural", placeholder="e.g. PERFS")
            yield Label("Description / Ghost Hint:")
            yield Input(
                value=tag.description if tag else "",
                id="tag-desc",
                placeholder="Short guidance shown in -- Tags: and placeholder",
            )
            yield Label("Template child tags (comma-separated, optional):")
            yield Input(
                value=", ".join(tag.template) if tag else "",
                id="tag-template",
                placeholder="OBJECTIVE, CONTEXT, CONSTRAINTS",
            )
            with Horizontal(classes="modal-actions"):
                yield Button("Cancel", id="tag-cancel")
                yield Button("Save Tag", variant="primary", id="tag-save")

    @on(Button.Pressed, "#tag-cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#tag-save")
    def _save(self) -> None:
        name = self.query_one("#tag-name", Input).value.strip().upper()
        desc = self.query_one("#tag-desc", Input).value.strip()
        kind = self.query_one("#tag-kind", Select).value
        plural = self.query_one("#tag-plural", Input).value.strip().upper()
        tmpl_raw = self.query_one("#tag-template", Input).value
        tmpl = [part.strip().upper() for part in tmpl_raw.split(",") if part.strip()]

        if not name or not re.fullmatch(r"[A-Z_][A-Z0-9_-]*", name):
            self.notify("Invalid tag name (use A-Z, 0-9, _).", severity="error")
            return
        if not desc:
            self.notify("Description is required.", severity="error")
            return

        self.dismiss(
            TagDef(
                name=name,
                kind="main" if kind == "main" else "complementary",
                plural=plural,
                description=desc,
                template=tmpl,
            )
        )


class SettingsScreen(ModalScreen[AppConfig | None]):
    """Settings modal for Templates toggle, workspace indexing, output, and tags."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
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

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-box"):
            yield Label("Settings", classes="modal-title")
            with VerticalScroll(id="settings-scroll"):
                with Horizontal(classes="setting-row"):
                    yield Label("Templates (expand assigned child tags on Tab)", classes="setting-label")
                    yield Switch(value=self.draft.templates_enabled, id="sw-templates")

                with Horizontal(classes="setting-row"):
                    yield Label("Strip empty tags on copy", classes="setting-label")
                    yield Switch(value=self.draft.strip_empty_tags, id="sw-strip")

                with Horizontal(classes="setting-row"):
                    yield Label("Respect .gitignore when indexing #files", classes="setting-label")
                    yield Switch(value=self.draft.respect_gitignore, id="sw-gitignore")

                with Horizontal(classes="setting-row"):
                    yield Label("After copy", classes="setting-label")
                    yield Select(
                        [("Copy & Close", "close"), ("Copy & Stay Open", "stay")],
                        value=self.draft.after_copy,
                        id="sel-after-copy",
                    )

                with Horizontal(classes="setting-row"):
                    yield Label("Indentation", classes="setting-label")
                    yield Select([(f"{n} spaces", n) for n in (2, 4)], value=self.draft.indent_spaces, id="sel-indent")

                yield Label("Tags & Templates (select to edit or delete):")
                yield OptionList(id="settings-tag-list")
                with Horizontal(classes="modal-actions"):
                    yield Button("+ New Tag", id="btn-new-tag")
                    yield Button("Edit Selected", id="btn-edit-tag")
                    yield Button("Delete Selected", id="btn-del-tag")

            with Horizontal(classes="modal-actions"):
                yield Button("Cancel", id="set-cancel")
                yield Button("Save", variant="primary", id="set-save")

    def on_mount(self) -> None:
        self._refresh_tag_list()

    def _refresh_tag_list(self) -> None:
        olist = self.query_one("#settings-tag-list", OptionList)
        olist.clear_options()
        for tag in self.draft.tags:
            badge = "MAIN" if tag.kind == "main" else "COMP"
            tmpl_info = f" -> [{', '.join(tag.template)}]" if tag.template else ""
            olist.add_option(Option(f"[{badge}] {tag.name}: {tag.description}{tmpl_info}", id=tag.name))

    @on(Button.Pressed, "#btn-new-tag")
    def _new_tag(self) -> None:
        def _on_done(new_tag: TagDef | None) -> None:
            if new_tag is None:
                return
            self.draft.tags = [t for t in self.draft.tags if t.name != new_tag.name]
            self.draft.tags.append(new_tag)
            self._refresh_tag_list()

        self.app.push_screen(TagEditorScreen(), _on_done)

    @on(Button.Pressed, "#btn-edit-tag")
    def _edit_tag(self) -> None:
        olist = self.query_one("#settings-tag-list", OptionList)
        if olist.highlighted is None:
            return
        opt = olist.get_option_at_index(olist.highlighted)
        existing = self.draft.tag_map().get(str(opt.id))
        if existing is None:
            return

        def _on_done(edited: TagDef | None) -> None:
            if edited is None:
                return
            self.draft.tags = [edited if t.name == existing.name else t for t in self.draft.tags]
            self._refresh_tag_list()

        self.app.push_screen(TagEditorScreen(existing), _on_done)

    @on(Button.Pressed, "#btn-del-tag")
    def _delete_tag(self) -> None:
        olist = self.query_one("#settings-tag-list", OptionList)
        if olist.highlighted is None:
            return
        opt = olist.get_option_at_index(olist.highlighted)
        self.draft.tags = [t for t in self.draft.tags if t.name != str(opt.id)]
        self._refresh_tag_list()

    @on(Button.Pressed, "#set-cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#set-save")
    def _save(self) -> None:
        self.draft.templates_enabled = self.query_one("#sw-templates", Switch).value
        self.draft.strip_empty_tags = self.query_one("#sw-strip", Switch).value
        self.draft.respect_gitignore = self.query_one("#sw-gitignore", Switch).value
        after_val = self.query_one("#sel-after-copy", Select).value
        self.draft.after_copy = "stay" if after_val == "stay" else "close"
        indent_val = self.query_one("#sel-indent", Select).value
        self.draft.indent_spaces = int(indent_val) if indent_val in (2, 4) else 2
        self.dismiss(self.draft)


class PromptWritApp(App[None]):
    """Floating TUI for composing structured XML prompts."""

    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("ctrl+enter", "copy_prompt", "Copy & Close", show=False),
        Binding("ctrl+s", "open_settings", "Settings", show=False),
        Binding("escape", "handle_escape", "Cancel", show=False),
    ]

    def __init__(self, cli_cwd: str | None = None, config_file: Path | None = None) -> None:
        super().__init__()
        self.config_file = config_file
        self.config = load_config(config_file)
        self.workspace_root = resolve_workspace_root(cli_cwd, self.config)
        self.workspace_files: list[str] = []
        self._active_trigger: ActiveTrigger | None = None
        self._autocomplete_items: list[tuple[str, TagDef | str]] = []
        self._suppress_change = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-bar"):
            yield Label("PromptWrit", id="app-title")
            yield Button(f"📁 {self.workspace_root.name}", id="workspace-btn")
            yield Button("⚙", id="settings-btn")

        with VerticalScroll(id="tags-panel") as tags_box:
            tags_box.border_title = "-- Tags:"
            yield Static("", id="tags-content")

        with Vertical(id="editor-container"):
            editor = PromptTextArea("", id="prompt-editor", soft_wrap=True)
            editor.border_title = "-- Prompt:"
            yield editor
            yield OptionList(id="autocomplete-popup")

        yield Static(
            "Tab: Accept / Next Slot   |   #: File Path   |   Ctrl+Enter: Copy & Close   |   Esc: Cancel",
            id="footer-bar",
        )

    def on_mount(self) -> None:
        self._reindex_workspace()
        self.query_one("#prompt-editor", PromptTextArea).focus()
        self._refresh_tags_legend()

    def _reindex_workspace(self) -> None:
        self.workspace_files = list_workspace_files(
            self.workspace_root,
            respect_gitignore=self.config.respect_gitignore,
            extra_ignores=self.config.extra_ignores,
        )
        self.query_one("#workspace-btn", Button).label = f"📁 {self.workspace_root.name}"

    def _refresh_tags_legend(self) -> None:
        editor = self.query_one("#prompt-editor", PromptTextArea)
        active = extract_active_tags(editor.text, self.config)
        legend = self.query_one("#tags-content", Static)
        if not active:
            legend.update("")
            return
        lines = [f"{name}: {desc}" for name, desc in active]
        legend.update("\n".join(lines))

    def is_autocomplete_visible(self) -> bool:
        return self.query_one("#autocomplete-popup", OptionList).has_class("visible")

    def hide_autocomplete(self) -> None:
        popup = self.query_one("#autocomplete-popup", OptionList)
        popup.remove_class("visible")
        popup.clear_options()
        self._active_trigger = None
        self._autocomplete_items = []

    def move_autocomplete(self, delta: int) -> None:
        popup = self.query_one("#autocomplete-popup", OptionList)
        count = popup.option_count
        if count == 0:
            return
        current = popup.highlighted or 0
        popup.highlighted = (current + delta) % count

    def _detect_trigger(self, text: str, cursor_idx: int) -> ActiveTrigger | None:
        before = text[:cursor_idx]
        tag_match = re.search(r"<([A-Za-z0-9_-]*)$", before)
        if tag_match:
            return ActiveTrigger(
                kind="tag",
                query=tag_match.group(1),
                start_index=tag_match.start(),
                end_index=cursor_idx,
            )
        file_match = re.search(r"#([^\s<>#]*)$", before)
        if file_match:
            return ActiveTrigger(
                kind="file",
                query=file_match.group(1),
                start_index=file_match.start(),
                end_index=cursor_idx,
            )
        return None

    def _update_autocomplete(self) -> None:
        editor = self.query_one("#prompt-editor", PromptTextArea)
        row, col = editor.cursor_location
        cursor_idx = _row_col_to_index(editor.text, row, col)
        trigger = self._detect_trigger(editor.text, cursor_idx)
        if trigger is None:
            self.hide_autocomplete()
            return

        popup = self.query_one("#autocomplete-popup", OptionList)
        popup.clear_options()
        self._autocomplete_items = []

        if trigger.kind == "tag":
            stack = get_tag_stack_at_cursor(editor.text, trigger.start_index)
            candidates = allowed_tags_for_context(stack, self.config)
            q = trigger.query.upper()
            matched = [t for t in candidates if t.name.startswith(q)] if q else candidates
            if not matched:
                self.hide_autocomplete()
                return
            for tag in matched:
                popup.add_option(Option(f"{tag.name:<13} | {tag.description}", id=tag.name))
                self._autocomplete_items.append(("tag", tag))
        else:
            matched_files = fuzzy_match_files(trigger.query, self.workspace_files, limit=10)
            if not matched_files:
                self.hide_autocomplete()
                return
            for idx, rel in enumerate(matched_files, start=1):
                popup.add_option(Option(f"{idx}. {rel}", id=rel))
                self._autocomplete_items.append(("file", rel))

        self._active_trigger = trigger
        popup.highlighted = 0
        popup.add_class("visible")

    def accept_autocomplete(self) -> None:
        popup = self.query_one("#autocomplete-popup", OptionList)
        if self._active_trigger is None or popup.highlighted is None:
            self.hide_autocomplete()
            return
        if popup.highlighted >= len(self._autocomplete_items):
            self.hide_autocomplete()
            return

        kind, payload = self._autocomplete_items[popup.highlighted]
        trigger = self._active_trigger
        editor = self.query_one("#prompt-editor", PromptTextArea)
        self.hide_autocomplete()

        if kind == "file" and isinstance(payload, str):
            start_rc = _index_to_row_col(editor.text, trigger.start_index)
            end_rc = _index_to_row_col(editor.text, trigger.end_index)
            self._suppress_change = True
            editor.replace(payload, start_rc, end_rc)
            self._suppress_change = False
            self._refresh_tags_legend()
            return

        if kind == "tag" and isinstance(payload, TagDef):
            start_rc = _index_to_row_col(editor.text, trigger.start_index)
            end_rc = _index_to_row_col(editor.text, trigger.end_index)
            base_indent = " " * start_rc[1]
            snippet, stops = expand_tag_snippet(payload, self.config, base_indent=base_indent)

            new_text = (
                editor.text[: trigger.start_index]
                + snippet
                + editor.text[trigger.end_index :]
            )
            pluralized = apply_auto_pluralization(new_text, self.config)

            self._suppress_change = True
            editor.text = pluralized
            self._suppress_change = False

            # Place cursor/selection on the first placeholder hint if present.
            if stops:
                first_hint = stops[0].hint
                if first_hint and first_hint in pluralized:
                    idx = pluralized.find(first_hint, trigger.start_index)
                    if idx != -1:
                        s_rc = _index_to_row_col(pluralized, idx)
                        e_rc = _index_to_row_col(pluralized, idx + len(first_hint))
                        editor.selection = Selection(s_rc, e_rc)
            self._refresh_tags_legend()

    def jump_next_tab_stop(self) -> bool:
        """Jump to the next known placeholder hint or empty tag after the cursor."""
        editor = self.query_one("#prompt-editor", PromptTextArea)
        text = editor.text
        row, col = editor.cursor_location
        cursor_idx = _row_col_to_index(text, row, col)
        # Advance past current selection if user is sitting on a selected hint.
        if editor.selection.start != editor.selection.end:
            sel_end = _row_col_to_index(text, *editor.selection.end)
            cursor_idx = max(cursor_idx, sel_end)

        best_span: tuple[int, int] | None = None
        for tag in self.config.tags:
            if not tag.description:
                continue
            token = f">{tag.description}</"
            found = text.find(token, cursor_idx)
            if found != -1:
                start = found + 1
                end = start + len(tag.description)
                if best_span is None or start < best_span[0]:
                    best_span = (start, end)

        if best_span is not None:
            editor.selection = Selection(
                _index_to_row_col(text, best_span[0]),
                _index_to_row_col(text, best_span[1]),
            )
            return True
        return False

    @on(TextArea.Changed, "#prompt-editor")
    def _on_editor_changed(self) -> None:
        if self._suppress_change:
            return
        self._refresh_tags_legend()
        self._update_autocomplete()

    @on(OptionList.OptionSelected, "#autocomplete-popup")
    def _on_option_clicked(self) -> None:
        self.accept_autocomplete()

    @on(Button.Pressed, "#workspace-btn")
    def _open_workspace_modal(self) -> None:
        def _on_selected(new_root: Path | None) -> None:
            if new_root is not None:
                self.workspace_root = new_root
                self.config.last_workspace = str(new_root)
                save_config(self.config, self.config_file)
                self._reindex_workspace()
                self.query_one("#prompt-editor", PromptTextArea).focus()

        self.push_screen(WorkspaceScreen(self.workspace_root), _on_selected)

    @on(Button.Pressed, "#settings-btn")
    def action_open_settings(self) -> None:
        def _on_saved(updated: AppConfig | None) -> None:
            if updated is not None:
                self.config = updated
                save_config(self.config, self.config_file)
                self._reindex_workspace()
                self._refresh_tags_legend()
            self.query_one("#prompt-editor", PromptTextArea).focus()

        self.push_screen(SettingsScreen(self.config), _on_saved)

    def action_copy_prompt(self) -> None:
        editor = self.query_one("#prompt-editor", PromptTextArea)
        hints = {t.description for t in self.config.tags if t.description}
        cleaned = clean_prompt_for_copy(
            editor.text,
            known_hints=hints,
            strip_empty_tags=self.config.strip_empty_tags,
        )
        if not cleaned:
            self.notify("Prompt is empty.", severity="warning")
            return
        if copy_to_clipboard(cleaned):
            self.notify("Copied prompt to clipboard.")
            if self.config.after_copy == "close":
                self.exit()
        else:
            self.notify("Clipboard copy failed (wl-copy / xclip unavailable).", severity="error")

    def action_handle_escape(self) -> None:
        if self.is_autocomplete_visible():
            self.hide_autocomplete()
        else:
            self.exit()
