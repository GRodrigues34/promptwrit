# PromptWrit

Standalone modern dark-mode desktop launcher (built with Python `PySide6`) for composing structured, uppercase XML prompts for agentic CLIs and IDEs (`Claude Code`, `Gemini CLI`, `Cursor`, `Antigravity`).

## Features
- **Independent Desktop Window:** Clean dark-slate Qt6 UI with XML syntax highlighting, dimmed ghost placeholder hints, and a pixel-accurate floating autocomplete popup.
- **Two-Pane Layout:** Read-only `-- Tags:` live legend on top + editable `-- Prompt:` code editor below.
- **Two-Tier Tag Hierarchy:**
  - **Main tags** (`FEATURE`, `BUG`, `UPDATE`, `REFACTOR`, `TEST`, `REVIEW`, `PLAN`, `DEBUG`, `DOCS`, `PROMPT`) at root, with automatic pluralization when `2+` instances of the same Main tag are added (`<FEATURES>...</FEATURES>`).
  - **Complementary tags** (`OBJECTIVE`, `CONTEXT`, `EXAMPLE`, `CONSTRAINTS`, `EXPECTED`, `ACTUAL`, `VERIFICATION`, `OUTPUT`) allowed at root or nested inside any tag.
- **Templates Toggle & Custom Tag Editor (`⚙`):** Enable/disable automatic template expansion on `Tab`, and create or customize templates for any Main or Complementary tag.
- **Workspace-Scoped `#file` Autocomplete (`📁`):** Fuzzy-searches relative file paths inside the active git root / workspace (respecting `.gitignore`) and inserts path-only references.
- **Clean Clipboard Copy (`Ctrl+Enter`):** Strips untouched placeholder hints and empty tags before copying.

## Run Locally
```bash
PYTHONPATH=src .venv/bin/python -m promptwrit --cwd /path/to/your/repo
```

## Run Tests
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v
```
