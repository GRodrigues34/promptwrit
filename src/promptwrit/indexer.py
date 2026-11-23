"""Workspace root resolution, .gitignore-aware file indexing, and fuzzy matching."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from promptwrit.schema import AppConfig


def find_git_root(start: Path) -> Path | None:
    """Walk upward from start to find the nearest .git directory."""
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_workspace_root(cli_cwd: str | None, config: AppConfig) -> Path:
    """Resolve the active workspace root directory."""
    if cli_cwd:
        p = Path(cli_cwd).expanduser().resolve()
        if p.exists() and p.is_dir():
            return find_git_root(p) or p

    for saved in (config.pinned_workspace, config.last_workspace):
        if saved:
            p = Path(saved).expanduser().resolve()
            if p.exists() and p.is_dir():
                return p

    cwd = Path.cwd().resolve()
    return find_git_root(cwd) or cwd


def _git_ls_files(root: Path) -> list[str] | None:
    """List non-ignored workspace files via git ls-files, or None if unavailable."""
    if not (root / ".git").exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if proc.returncode != 0:
        return None
    return [line for line in proc.stdout.splitlines() if line.strip()]


def list_workspace_files(
    root: Path,
    respect_gitignore: bool = True,
    extra_ignores: list[str] | None = None,
) -> list[str]:
    """Return sorted relative file paths under root, respecting ignore rules."""
    ignores = set(extra_ignores or [".git", "node_modules", ".venv", "__pycache__", "dist", "build"])

    if respect_gitignore:
        git_files = _git_ls_files(root)
        if git_files is not None:
            filtered = [
                rel
                for rel in git_files
                if not any(part in ignores for part in Path(rel).parts)
            ]
            return sorted(filtered)

    results: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in ignores and not d.startswith("."))
        rel_dir = Path(dirpath).relative_to(root)
        for fname in sorted(filenames):
            if fname in ignores:
                continue
            rel_path = (rel_dir / fname).as_posix() if rel_dir != Path(".") else fname
            results.append(rel_path)
    return results


def _fuzzy_score(query: str, path_str: str) -> int | None:
    """Return a higher score for better matches, or None if query does not match."""
    q = query.lower()
    if not q:
        return 0
    path_lower = path_str.lower()
    name_lower = Path(path_str).name.lower()

    if name_lower.startswith(q):
        return 1000 - len(name_lower)
    if q in name_lower:
        return 800 - len(name_lower)
    if q in path_lower:
        return 600 - len(path_lower)

    # Subsequence match across the relative path.
    qi = 0
    for ch in path_lower:
        if ch == q[qi]:
            qi += 1
            if qi == len(q):
                return 300 - len(path_lower)
    return None


def fuzzy_match_files(query: str, files: list[str], limit: int = 12) -> list[str]:
    """Return up to `limit` relative paths matching `query`, best matches first."""
    if not query.strip():
        return files[:limit]

    scored: list[tuple[int, str]] = []
    for rel in files:
        score = _fuzzy_score(query.strip(), rel)
        if score is not None:
            scored.append((score, rel))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [rel for _, rel in scored[:limit]]
