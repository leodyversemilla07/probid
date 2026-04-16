"""Single-line truncating text component."""

from __future__ import annotations

from probid_tui.core.ansi_utils import truncate_to_width
from probid_tui.core.component import Component


class TruncatedText(Component):
    def __init__(self, text: str = "", padding_x: int = 0, padding_y: int = 0):
        self.text = text
        self.padding_x = max(0, int(padding_x))
        self.padding_y = max(0, int(padding_y))

    def render(self, width: int) -> list[str]:
        width = max(1, width)
        inner = max(1, width - (self.padding_x * 2))
        line = (" " * self.padding_x) + truncate_to_width(self.text, inner, pad=True) + (" " * self.padding_x)
        out = [" " * width for _ in range(self.padding_y)]
        out.append(line[:width].ljust(width))
        out.extend([" " * width for _ in range(self.padding_y)])
        return out

