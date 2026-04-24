"""Minimal markdown-to-text renderer component."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from probid_tui.components.text import Text


@dataclass(frozen=True)
class DefaultTextStyle:
    color: Callable[[str], str] | None = None
    bg_color: Callable[[str], str] | None = None
    bold: bool = False
    italic: bool = False
    strikethrough: bool = False
    underline: bool = False


@dataclass(frozen=True)
class MarkdownTheme:
    heading: Callable[[str], str] = lambda s: s
    link: Callable[[str], str] = lambda s: s
    link_url: Callable[[str], str] = lambda s: s
    code: Callable[[str], str] = lambda s: s
    code_block: Callable[[str], str] = lambda s: s
    code_block_border: Callable[[str], str] = lambda s: s
    quote: Callable[[str], str] = lambda s: s
    quote_border: Callable[[str], str] = lambda s: s
    hr: Callable[[str], str] = lambda s: s
    list_bullet: Callable[[str], str] = lambda s: s
    bold: Callable[[str], str] = lambda s: s
    italic: Callable[[str], str] = lambda s: s
    strikethrough: Callable[[str], str] = lambda s: s
    underline: Callable[[str], str] = lambda s: s


class Markdown(Text):
    def __init__(
        self,
        text: str = "",
        padding_x: int = 1,
        padding_y: int = 1,
        theme: MarkdownTheme | None = None,
        default_style: DefaultTextStyle | None = None,
    ):
        super().__init__("", padding_x=padding_x, padding_y=padding_y)
        self._source = text
        self.theme = theme or MarkdownTheme()
        self.default_style = default_style or DefaultTextStyle()
        self.set_text(text)

    def set_text(self, text: str) -> None:
        self._source = text
        rendered = self._render_markdown(text)
        super().set_text(rendered)

    def _render_markdown(self, source: str) -> str:
        out: list[str] = []
        for line in source.splitlines():
            if line.startswith("#"):
                out.append(self.theme.heading(line.lstrip("# ").strip()))
            elif line.startswith(">"):
                out.append(self.theme.quote(line))
            elif line.startswith(("-", "*", "+")):
                out.append(self.theme.list_bullet("•") + " " + line[1:].strip())
            elif line.startswith("```"):
                out.append(self.theme.code_block_border(line))
            else:
                out.append(line)
        return "\n".join(out)
