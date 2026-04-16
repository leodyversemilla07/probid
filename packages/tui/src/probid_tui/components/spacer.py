"""Vertical spacer component."""

from __future__ import annotations

from probid_tui.core.component import Component


class Spacer(Component):
    def __init__(self, lines: int = 1):
        self.lines = max(0, int(lines))

    def render(self, width: int) -> list[str]:
        return [" " * max(1, width) for _ in range(self.lines)]

