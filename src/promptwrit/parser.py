"""XML tag parsing, context scoping, auto-pluralization, and clean copy formatting."""

from __future__ import annotations

import re
from dataclasses import dataclass

from promptwrit.schema import AppConfig, TagDef

_TAG_TOKEN_RE = re.compile(r"<(/?)([A-Za-z_][A-Za-z0-9_-]*)\s*>")
_LEAF_TAG_RE = re.compile(r"<([A-Za-z_][A-Za-z0-9_-]*)>([^<>]*)</\1>", re.DOTALL)


@dataclass(frozen=True)
class TabStop:
    """Represents a placeholder slot inside an expanded XML block."""

    start: int
    end: int
    hint: str


def get_tag_stack_at_cursor(text: str, cursor_index: int) -> list[str]:
    """Return the stack of open XML tag names before cursor_index."""
    stack: list[str] = []
    prefix = text[: max(0, cursor_index)]
    for match in _TAG_TOKEN_RE.finditer(prefix):
        is_closing = match.group(1) == "/"
        name = match.group(2).upper()
        if not is_closing:
            stack.append(name)
        elif name in stack:
            # Pop back to the matching opening tag to tolerate malformed drafts.
            idx = len(stack) - 1 - stack[::-1].index(name)
            del stack[idx:]
    return stack


def allowed_tags_for_context(stack: list[str], config: AppConfig) -> list[TagDef]:
    """Return tags permitted at the current nesting depth.

    Root (empty stack) allows Main and Complementary tags.
    Inside a plural wrapper (e.g. PROMPTS) allows its matching Main tag + Complementary tags.
    Inside any other open tag allows Complementary tags only.
    """
    if not stack:
        return list(config.tags)

    top = stack[-1]
    matching_main = [
        t for t in config.main_tags() if t.plural == top and t.plural != t.name
    ]
    return matching_main + config.complementary_tags()


def extract_active_tags(text: str, config: AppConfig) -> list[tuple[str, str]]:
    """Return unique (TAG_NAME, description) pairs present in text for `-- Tags:`.

    Plural wrapper tags (e.g. FEATURES) are excluded so only singular descriptions show.
    Unknown tags appear with `(custom)` as their description.
    """
    tag_map = config.tag_map()
    plurals = config.plural_set()
    seen: set[str] = set()
    result: list[tuple[str, str]] = []

    for match in _TAG_TOKEN_RE.finditer(text):
        is_closing = match.group(1) == "/"
        if is_closing:
            continue
        name = match.group(2).upper()
        if name in plurals or name in seen:
            continue
        seen.add(name)
        desc = tag_map[name].description if name in tag_map else "(custom)"
        result.append((name, desc))

    return result


def expand_tag_snippet(
    tag: TagDef,
    config: AppConfig,
    base_indent: str = "",
) -> tuple[str, list[TabStop]]:
    """Build the expanded XML string and TabStop offsets for a tag.

    When `config.templates_enabled` is True and `tag.template` is non-empty,
    expands child tags with standardized placeholder hints. Otherwise expands
    a single `<TAG>hint</TAG>` block.
    """
    indent_unit = " " * max(1, config.indent_spaces)
    tag_map = config.tag_map()

    if config.templates_enabled and tag.template:
        lines = [f"<{tag.name}>"]
        stops: list[TabStop] = []
        offset = len(lines[0]) + 1  # +1 for newline

        for child_name in tag.template:
            child_def = tag_map.get(child_name)
            hint = child_def.description if child_def else ""
            prefix = f"{base_indent}{indent_unit}<{child_name}>"
            suffix = f"</{child_name}>"
            start = offset + len(prefix)
            end = start + len(hint)
            stops.append(TabStop(start=start, end=end, hint=hint))
            line = f"{prefix}{hint}{suffix}"
            lines.append(line)
            offset += len(line) + 1

        lines.append(f"{base_indent}</{tag.name}>")
        return "\n".join(lines), stops

    hint = tag.description
    open_tag = f"<{tag.name}>"
    close_tag = f"</{tag.name}>"
    text = f"{open_tag}{hint}{close_tag}"
    stops = [TabStop(start=len(open_tag), end=len(open_tag) + len(hint), hint=hint)]
    return text, stops


def _find_top_level_blocks(text: str, tag_name: str) -> list[tuple[int, int]]:
    """Find (start, end) spans of top-level `<TAG>...</TAG>` blocks."""
    blocks: list[tuple[int, int]] = []
    depth = 0
    block_start = -1

    for match in _TAG_TOKEN_RE.finditer(text):
        is_closing = match.group(1) == "/"
        name = match.group(2).upper()
        if not is_closing:
            if depth == 0 and name == tag_name:
                block_start = match.start()
            depth += 1
        else:
            depth = max(0, depth - 1)
            if depth == 0 and block_start != -1 and name == tag_name:
                blocks.append((block_start, match.end()))
                block_start = -1

    return blocks


def _indent_block(block: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" if line.strip() else line for line in block.splitlines())


def _dedent_block(block: str, prefix: str) -> str:
    lines = []
    for line in block.splitlines():
        if line.startswith(prefix):
            lines.append(line[len(prefix) :])
        else:
            lines.append(line)
    return "\n".join(lines)


def apply_auto_pluralization(text: str, config: AppConfig) -> str:
    """Wrap 2+ root Main tags in their plural tag, and unwrap if reduced to 1."""
    indent_unit = " " * max(1, config.indent_spaces)
    updated = text

    for tag in config.main_tags():
        if not tag.plural or tag.plural == tag.name:
            continue

        # 1. Check existing plural wrappers: unwrap if <= 1 child Main block remains.
        plural_spans = _find_top_level_blocks(updated, tag.plural)
        for p_start, p_end in reversed(plural_spans):
            inner = updated[p_start + len(f"<{tag.plural}>") : p_end - len(f"</{tag.plural}>")]
            inner_stripped = inner.strip("\n")
            dedented = _dedent_block(inner_stripped, indent_unit)
            child_spans = _find_top_level_blocks(dedented, tag.name)
            if len(child_spans) <= 1:
                updated = updated[:p_start] + dedented + updated[p_end:]

        # 2. Check root-level singular blocks: wrap if 2+ exist.
        root_spans = _find_top_level_blocks(updated, tag.name)
        if len(root_spans) >= 2:
            first_start = root_spans[0][0]
            last_end = root_spans[-1][1]
            # Only wrap contiguous/root blocks from first to last; preserve any text outside.
            blocks_text = [updated[s:e] for s, e in root_spans]
            indented_children = "\n".join(_indent_block(b, indent_unit) for b in blocks_text)
            wrapped = f"<{tag.plural}>\n{indented_children}\n</{tag.plural}>"

            # Replace the span from first_start to last_end if nothing non-whitespace sits between.
            between_parts = [
                updated[root_spans[i][1] : root_spans[i + 1][0]].strip()
                for i in range(len(root_spans) - 1)
            ]
            if all(part == "" for part in between_parts):
                updated = updated[:first_start] + wrapped + updated[last_end:]

    return updated


def clean_prompt_for_copy(
    text: str,
    known_hints: set[str],
    strip_empty_tags: bool = True,
) -> str:
    """Strip untouched ghost hints and optionally remove empty tags before copying."""
    cleaned = text

    def _replace_hint(match: re.Match[str]) -> str:
        tag_name = match.group(1)
        body = match.group(2)
        if body.strip() in known_hints:
            return f"<{tag_name}></{tag_name}>"
        return match.group(0)

    cleaned = _LEAF_TAG_RE.sub(_replace_hint, cleaned)

    if strip_empty_tags:
        # Iteratively remove empty tags (e.g., <EXAMPLE></EXAMPLE> or empty containers).
        empty_tag_re = re.compile(r"^[ \t]*<([A-Za-z_][A-Za-z0-9_-]*)>\s*</\1>[ \t]*\n?", re.MULTILINE)
        prev = None
        while prev != cleaned:
            prev = cleaned
            cleaned = empty_tag_re.sub("", cleaned)

    # Collapse 3+ consecutive newlines to at most 2 and trim edges.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
