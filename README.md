# PromptWrit

Floating terminal TUI (built with Python `textual`) for composing structured, uppercase XML prompts for agentic CLIs and IDEs (`Claude Code`, `Gemini CLI`, `Cursor`, `Antigravity`).

## Features
- **Two-Pane Dark Slate UI:** Read-only `-- Tags:` live legend on top + editable `-- Prompt:` box below.
- **Two-Tier Tag Hierarchy:**
  - **Main tags** (`FEATURE`, `BUG`, `UPDATE`, `REFACTOR`, `TEST`, `REVIEW`, `PLAN`, `DEBUG`, `DOCS`, `PROMPT`) at root, with automatic pluralization when `2+` instances of the same Main tag are added (`<FEATURES>...</FEATURES>`).
  - **Complementary tags** (`OBJECTIVE`, `CONTEXT`, `EXAMPLE`, `CONSTRAINTS`, `EXPECTED`, `ACTUAL`, `VERIFICATION`, `OUTPUT`) allowed at root or nested inside any tag.
- **Templates Toggle & Custom Tag Editor (`⚙`):** Enable/disable automatic template expansion on `Tab`, and create or customize templates for any Main or Complementary tag.
- **Workspace-Scoped `#file` Autocomplete (`📁`):** Fuzzy-searches relative file paths inside the active git root / workspace (respecting `.gitignore`) and inserts path-only references.
- **Clean Clipboard Copy (`Ctrl+Enter`):** Strips untouched placeholder hints and empty tags before copying.

## Run Locally
```bash
.venv/bin/python -m promptwrit --cwd /path/to/your/repo
```

## Run Tests
```bash
.venv/bin/pytest -v
```
