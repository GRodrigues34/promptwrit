# PromptWrit

Standalone modern dark-mode desktop launcher (built with Python `PySide6`) for composing structured, uppercase XML prompts for agentic CLIs and IDEs (`Claude Code`, `Gemini CLI`, `Cursor`, `Antigravity`).

Default tags are tailored for software development, and all tags and templates can be customized in Settings for research, content creation, or any other workflow.

## Features
- **Independent Desktop Window & Instant Launch:** Clean dark-slate Qt6 UI with XML syntax highlighting, dimmed non-editable ghost hints, and a cursor-anchored autocomplete popup. Runs as a lightweight single-instance background daemon for instant `Ctrl + '` launch.
- **Two-Pane Layout:** Read-only `-- Tags:` live legend on top + editable `-- Prompt:` code editor below.
- **Two-Tier Tag Hierarchy:**
  - **Main tags** (`FEATURE`, `BUG`, `UPDATE`, `REFACTOR`, `TEST`, `REVIEW`, `PLAN`, `DEBUG`, `DOCS`, `PROMPT`) at root, with automatic pluralization when `2+` instances of the same Main tag are added (`<FEATURES>...</FEATURES>`).
  - **Complementary tags** (`OBJECTIVE`, `CONTEXT`, `EXAMPLE`, `CONSTRAINTS`, `EXPECTED`, `ACTUAL`, `VERIFICATION`, `OUTPUT`) allowed at root or nested inside any tag.
- **Templates Toggle & Custom Tag Editor (`⚙`):** Enable/disable automatic template expansion on `Tab`, create custom tags, and edit or assign templates for any Main or Complementary tag.
- **Workspace-Scoped `#file` Autocomplete (`📁`):** Fuzzy-searches relative file paths inside the active git root / workspace (respecting `.gitignore`) and inserts path-only references.
- **Clean Clipboard Copy (`Ctrl+Enter`):** Strips untouched placeholder hints and empty tags before copying.

## Shortcuts
- `Ctrl + '`: Open / focus PromptWrit (after Linux install)
- `<`: Open context-aware tag autocomplete (`Tab` or `Enter` to insert)
- `#`: Open workspace-scoped `#file` path autocomplete
- `Tab`: Jump to the next tag slot (wraps around from the last tag to the first)
- `Ctrl + Enter`: Copy clean XML prompt to clipboard and hide/close
- `Esc`: Close autocomplete popup or hide window
- `Ctrl + Q`: Quit background daemon

## Install on Linux (Executable + `Ctrl + '` Shortcut)
Download the latest `promptwrit-linux-x86_64.tar.gz` from [GitHub Releases](https://github.com/GRodrigues34/promptwrit/releases) (or clone this repo) and run:
```bash
./install.sh
```
This installs the standalone app to `~/.local/share/promptwrit` (symlinked at `~/.local/bin/promptwrit`), creates a `.desktop` launcher, enables login autostart for the background daemon, and binds `Ctrl + '` on GNOME.

To uninstall:
```bash
./uninstall.sh        # keeps ~/.config/promptwrit
./uninstall.sh --purge # also removes saved config
```

*(On Ubuntu/Debian X11, ensure `libxcb-cursor0` is installed: `sudo apt install -y libxcb-cursor0`.)*

## Run Locally (From Source)
```bash
git clone https://github.com/GRodrigues34/promptwrit.git
cd promptwrit
python3 -m venv .venv
.venv/bin/pip install PySide6 pyperclip
PYTHONPATH=src .venv/bin/python -m promptwrit --cwd /path/to/your/repo
```

## Run Tests
```bash
.venv/bin/pip install pytest
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v
```

## License
[MIT](LICENSE)
