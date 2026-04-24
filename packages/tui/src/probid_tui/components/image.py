"""Image component using terminal-image helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from probid_tui.core.component import Component
from probid_tui.terminal_image import ImageRenderOptions, render_image


@dataclass(frozen=True)
class ImageTheme:
    fallback_color: Callable[[str], str] = lambda s: s


@dataclass(frozen=True)
class ImageOptions:
    max_width_cells: int | None = None
    max_height_cells: int | None = None
    filename: str | None = None


class Image(Component):
    def __init__(
        self,
        base64_data: str,
        mime_type: str,
        theme: ImageTheme | None = None,
        options: ImageOptions | None = None,
    ):
        self.base64_data = base64_data
        self.mime_type = mime_type
        self.theme = theme or ImageTheme()
        self.options = options or ImageOptions()

    def render(self, width: int) -> list[str]:
        rendered = render_image(
            self.base64_data,
            self.mime_type,
            ImageRenderOptions(
                width_cells=self.options.max_width_cells,
                height_cells=self.options.max_height_cells,
                filename=self.options.filename,
            ),
        )
        if rendered.startswith("[image"):
            rendered = self.theme.fallback_color(rendered)
        return [rendered[: max(1, width)]]
