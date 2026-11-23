"""XML syntax and ghost-placeholder highlighter for PromptWrit's Qt editor."""

from __future__ import annotations

import re

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument


class PromptXmlHighlighter(QSyntaxHighlighter):
    """Highlights uppercase XML tags, #file references, and dimmed ghost hints."""

    def __init__(self, parent: QTextDocument, known_hints: set[str] | None = None) -> None:
        super().__init__(parent)
        self.known_hints: set[str] = known_hints or set()

        self._tag_fmt = QTextCharFormat()
        self._tag_fmt.setForeground(QColor("#7eb2d6"))
        self._tag_fmt.setFontWeight(QFont.Weight.DemiBold)

        self._file_fmt = QTextCharFormat()
        self._file_fmt.setForeground(QColor("#8fbcbb"))

        self._hint_fmt = QTextCharFormat()
        self._hint_fmt.setForeground(QColor("#5f6b7d"))
        self._hint_fmt.setFontItalic(True)

        self._tag_re = QRegularExpression(r"</?[A-Za-z_][A-Za-z0-9_-]*>")
        self._file_re = QRegularExpression(r"(?:^|\s)(#[A-Za-z0-9_./-]+)")
        self._leaf_re = re.compile(r"<([A-Za-z_][A-Za-z0-9_-]*)>([^<>]+)</\1>")

    def set_known_hints(self, hints: set[str]) -> None:
        """Update the set of canonical ghost hints and rehighlight."""
        self.known_hints = hints
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt override)
        tag_it = self._tag_re.globalMatch(text)
        while tag_it.hasNext():
            m = tag_it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), self._tag_fmt)

        file_it = self._file_re.globalMatch(text)
        while file_it.hasNext():
            m = file_it.next()
            self.setFormat(m.capturedStart(1), m.capturedLength(1), self._file_fmt)

        for match in self._leaf_re.finditer(text):
            body = match.group(2)
            if body.strip() in self.known_hints:
                self.setFormat(match.start(2), len(body), self._hint_fmt)
