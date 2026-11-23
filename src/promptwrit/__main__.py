"""CLI entrypoint for PromptWrit."""

from __future__ import annotations

import argparse

from promptwrit.app import PromptWritApp


def main() -> None:
    """Parse CLI arguments and launch the PromptWrit TUI."""
    parser = argparse.ArgumentParser(
        prog="promptwrit",
        description="Floating TUI for composing structured uppercase XML prompts.",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Workspace directory to index for #file autocomplete (defaults to git root or last used).",
    )
    args = parser.parse_args()
    app = PromptWritApp(cli_cwd=args.cwd)
    app.run()


if __name__ == "__main__":
    main()
