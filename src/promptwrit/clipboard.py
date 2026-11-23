"""Cross-platform clipboard integration (Wayland, X11, pyperclip fallback)."""

from __future__ import annotations

import shutil
import subprocess

import pyperclip


def copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard. Returns True on success."""
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
        if shutil.which(cmd[0]):
            try:
                proc = subprocess.run(cmd, input=text, text=True, timeout=2, check=False)
                if proc.returncode == 0:
                    return True
            except (OSError, subprocess.SubprocessError):
                continue

    try:
        pyperclip.copy(text)
        return True
    except pyperclip.PyperclipException:
        return False
