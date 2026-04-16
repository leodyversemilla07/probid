"""Box container with padding and optional background application."""

from __future__ import annotations

from collections.abc import Callable

from probid_tui.core.ansi_utils import truncate_to_width
from probid_tui.core.tui_runtime import Container


class Box(Container):
    def __init__(
        self,
        padding_x: int = 1,
        padding_y: int = 1,
        bg_fn: Callable[[str], str] | None = None,
    ):
        super().__init__()
        self.padding_x = max(0, int(padding_x))
        self.padding_y = max(0, int(padding_y))
        self._bg_fn = bg_fn

    def set_bg_fn(self, bg_fn: Callable[[str], str] | None) -> None:
        self._bg_fn = bg_fn

    def _bg(self, line: str) -> str:
        return self._bg_fn(line) if self._bg_fn else line

    def render(self, width: int) -> list[str]:
        width = max(1, width)
        inner = max(1, width - (self.padding_x * 2))
        lines: list[str] = []
        for _ in range(self.padding_y):
            lines.append(self._bg(" " * width))
        for child in self.children:
            for line in child.render(inner):
                body = truncate_to_width(line, inner, pad=True)
                lines.append(self._bg((" " * self.padding_x) + body + (" " * self.padding_x)))
        for _ in range(self.padding_y):
            lines.append(self._bg(" " * width))
        return lines

