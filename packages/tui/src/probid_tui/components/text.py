"""Text component with wrapping and padding."""

from __future__ import annotations

from collections.abc import Callable

from probid_tui.core.ansi_utils import truncate_to_width, wrap_text_with_ansi
from probid_tui.core.component import Component


class Text(Component):
    def __init__(
        self,
        text: str = "",
        padding_x: int = 1,
        padding_y: int = 1,
        bg_fn: Callable[[str], str] | None = None,
    ):
        self._text = text
        self._padding_x = max(0, int(padding_x))
        self._padding_y = max(0, int(padding_y))
        self._bg_fn = bg_fn

    def set_text(self, text: str) -> None:
        self._text = text

    def set_custom_bg_fn(self, bg_fn: Callable[[str], str] | None) -> None:
        self._bg_fn = bg_fn

    def _bg(self, line: str) -> str:
        return self._bg_fn(line) if self._bg_fn else line

    def render(self, width: int) -> list[str]:
        width = max(1, width)
        inner = max(1, width - (self._padding_x * 2))
        lines = wrap_text_with_ansi(self._text, inner)
        out: list[str] = []
        for _ in range(self._padding_y):
            out.append(self._bg(" " * width))
        for line in lines:
            body = truncate_to_width(line, inner, pad=True)
            out.append(self._bg((" " * self._padding_x) + body + (" " * self._padding_x)))
        for _ in range(self._padding_y):
            out.append(self._bg(" " * width))
        return out
