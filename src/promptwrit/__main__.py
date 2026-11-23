"""CLI entrypoint for PromptWrit desktop window."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from promptwrit.app import PromptWritWindow


def main() -> None:
    """Parse CLI arguments and launch the standalone PromptWrit desktop window."""
    parser = argparse.ArgumentParser(
        prog="promptwrit",
        description="Modern dark-mode desktop launcher for composing structured XML prompts.",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Workspace directory to index for #file autocomplete (defaults to git root or last used).",
    )
    args = parser.parse_args()

    qt_app = QApplication(sys.argv[:1])
    qt_app.setApplicationName("PromptWrit")
    window = PromptWritWindow(cli_cwd=args.cwd)
    window.show()
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
