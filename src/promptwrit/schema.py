"""Tag schema, default templates, and persistent configuration for PromptWrit."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

TagKind = Literal["main", "complementary"]


@dataclass
class TagDef:
    """Definition of a Main or Complementary XML tag."""

    name: str
    kind: TagKind
    description: str
    plural: str = ""
    template: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = self.name.strip().upper()
        if self.kind == "main" and not self.plural:
            self.plural = f"{self.name}S"
        elif self.plural:
            self.plural = self.plural.strip().upper()
        self.template = [t.strip().upper() for t in self.template if t.strip()]


@dataclass
class AppConfig:
    """User configuration and tag schema for PromptWrit."""

    templates_enabled: bool = True
    strip_empty_tags: bool = True
    respect_gitignore: bool = True
    extra_ignores: list[str] = field(
        default_factory=lambda: [".git", "node_modules", ".venv", "__pycache__", "dist", "build"]
    )
    indent_spaces: int = 2
    after_copy: Literal["close", "stay"] = "close"
    theme: str = "dark_slate"
    last_workspace: str = ""
    pinned_workspace: str = ""
    tags: list[TagDef] = field(default_factory=list)

    def tag_map(self) -> dict[str, TagDef]:
        """Return uppercase tag name -> TagDef mapping."""
        return {tag.name: tag for tag in self.tags}

    def plural_set(self) -> set[str]:
        """Return set of plural wrapper names distinct from their singular form."""
        return {
            tag.plural
            for tag in self.tags
            if tag.kind == "main" and tag.plural and tag.plural != tag.name
        }

    def main_tags(self) -> list[TagDef]:
        """Return all Main tags."""
        return [tag for tag in self.tags if tag.kind == "main"]

    def complementary_tags(self) -> list[TagDef]:
        """Return all Complementary tags."""
        return [tag for tag in self.tags if tag.kind == "complementary"]


def default_tags() -> list[TagDef]:
    """Return the built-in software development Main and Complementary tags."""
    return [
        # Main tags
        TagDef(
            name="FEATURE",
            kind="main",
            plural="FEATURES",
            description="Build a new capability or user-facing behavior",
            template=["OBJECTIVE", "CONTEXT", "EXAMPLE", "CONSTRAINTS", "VERIFICATION"],
        ),
        TagDef(
            name="BUG",
            kind="main",
            plural="BUGS",
            description="Fix broken or unexpected behavior",
            template=["EXPECTED", "ACTUAL", "CONTEXT", "CONSTRAINTS", "VERIFICATION"],
        ),
        TagDef(
            name="UPDATE",
            kind="main",
            plural="UPDATES",
            description="Modify existing behavior, dependencies, or UI without adding a new feature",
            template=["OBJECTIVE", "CONTEXT", "CONSTRAINTS", "VERIFICATION"],
        ),
        TagDef(
            name="REFACTOR",
            kind="main",
            plural="REFACTORS",
            description="Restructure code without changing external behavior",
            template=["OBJECTIVE", "CONTEXT", "CONSTRAINTS", "VERIFICATION"],
        ),
        TagDef(
            name="TEST",
            kind="main",
            plural="TESTS",
            description="Write, fix, or expand automated tests",
            template=["OBJECTIVE", "CONTEXT", "EXPECTED", "CONSTRAINTS", "VERIFICATION"],
        ),
        TagDef(
            name="REVIEW",
            kind="main",
            plural="REVIEWS",
            description="Audit code, architecture, or a diff for issues",
            template=["OBJECTIVE", "CONTEXT", "CONSTRAINTS", "OUTPUT"],
        ),
        TagDef(
            name="PLAN",
            kind="main",
            plural="PLANS",
            description="Design an approach, trade-offs, or architecture before writing code",
            template=["OBJECTIVE", "CONTEXT", "CONSTRAINTS", "OUTPUT"],
        ),
        TagDef(
            name="DEBUG",
            kind="main",
            plural="DEBUGS",
            description="Find root cause or explain why something happens without editing yet",
            template=["EXPECTED", "ACTUAL", "CONTEXT", "OUTPUT"],
        ),
        TagDef(
            name="DOCS",
            kind="main",
            plural="DOCS",
            description="Write or update READMEs, docstrings, or technical documentation",
            template=["OBJECTIVE", "CONTEXT", "EXAMPLE", "CONSTRAINTS"],
        ),
        TagDef(
            name="PROMPT",
            kind="main",
            plural="PROMPTS",
            description="Freeform prompt block (write anything, #file paths, or Complementary tags)",
            template=[],
        ),
        # Complementary tags
        TagDef(
            name="OBJECTIVE",
            kind="complementary",
            description="Exact outcome or goal expected",
        ),
        TagDef(
            name="CONTEXT",
            kind="complementary",
            description="Repo state, background, or #file paths",
        ),
        TagDef(
            name="EXAMPLE",
            kind="complementary",
            description="Existing #files to mirror, usage examples, or sample I/O",
        ),
        TagDef(
            name="CONSTRAINTS",
            kind="complementary",
            description="Rules, limits, or what NOT to touch",
        ),
        TagDef(
            name="EXPECTED",
            kind="complementary",
            description="What should happen",
        ),
        TagDef(
            name="ACTUAL",
            kind="complementary",
            description="What happens instead, error message, or stack trace",
        ),
        TagDef(
            name="VERIFICATION",
            kind="complementary",
            description="How to test or prove it works",
        ),
        TagDef(
            name="OUTPUT",
            kind="complementary",
            description="Desired response format (e.g., plan only, diff only, no code edits)",
        ),
    ]


def default_config() -> AppConfig:
    """Create a fresh AppConfig populated with default tags."""
    return AppConfig(tags=default_tags())


def config_path(custom_path: Path | None = None) -> Path:
    """Return the path to the PromptWrit JSON config file."""
    if custom_path is not None:
        return custom_path
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "promptwrit" / "config.json"


def load_config(custom_path: Path | None = None) -> AppConfig:
    """Load configuration from disk, or return defaults if missing or invalid."""
    path = config_path(custom_path)
    if not path.exists():
        return default_config()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_config()

    raw_tags = raw.get("tags")
    tags = (
        [TagDef(**item) for item in raw_tags if isinstance(item, dict) and "name" in item]
        if isinstance(raw_tags, list) and raw_tags
        else default_tags()
    )
    return AppConfig(
        templates_enabled=bool(raw.get("templates_enabled", True)),
        strip_empty_tags=bool(raw.get("strip_empty_tags", True)),
        respect_gitignore=bool(raw.get("respect_gitignore", True)),
        extra_ignores=list(raw.get("extra_ignores", AppConfig().extra_ignores)),
        indent_spaces=int(raw.get("indent_spaces", 2)),
        after_copy=raw.get("after_copy", "close") if raw.get("after_copy") in ("close", "stay") else "close",
        theme=str(raw.get("theme", "dark_slate")),
        last_workspace=str(raw.get("last_workspace", "")),
        pinned_workspace=str(raw.get("pinned_workspace", "")),
        tags=tags,
    )


def save_config(config: AppConfig, custom_path: Path | None = None) -> Path:
    """Persist configuration to disk and return the written path."""
    path = config_path(custom_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
    return path
