"""Pi-like editor surface rendering (rails + visible lines + scroll indicators)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EditorSurfaceConfig:
    max_visible_lines: int = 5
    rail_char: str = "─"


class EditorSurface:
    """Render a pi-style input surface with top/bottom rails.

    This is a lightweight, renderer-only abstraction intended for terminal
    modes that still use blocking line input. It mirrors pi's visual shape:
    top rail, content lines, bottom rail, and optional scroll indicators.
    """

    def __init__(self, config: EditorSurfaceConfig | None = None):
        self.config = config or EditorSurfaceConfig()

    def render(self, width: int, lines: list[str], scroll_offset: int = 0) -> list[str]:
        width = max(20, width)
        max_visible = max(1, self.config.max_visible_lines)

        total_lines = len(lines)
        visible = lines[scroll_offset : scroll_offset + max_visible]
        lines_above = scroll_offset
        lines_below = max(0, total_lines - (scroll_offset + len(visible)))

        def _rail_with_indicator(prefix: str, count: int) -> str:
            indicator = f"─── {prefix} {count} more "
            if len(indicator) >= width:
                return indicator[:width]
            return indicator + (self.config.rail_char * (width - len(indicator)))

        if lines_above > 0:
            top = _rail_with_indicator("↑", lines_above)
        else:
            top = self.config.rail_char * width

        if lines_below > 0:
            bottom = _rail_with_indicator("↓", lines_below)
        else:
            bottom = self.config.rail_char * width

        body = [line[:width].ljust(width) for line in visible]
        if not body:
            body = ["".ljust(width)]

        return [top, *body, bottom]
