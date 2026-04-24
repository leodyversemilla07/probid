"""Theme system for probid terminal UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThemeColors:
    """Color palette for terminal output."""

    primary: str = "cyan"
    secondary: str = "blue"
    accent: str = "magenta"
    success: str = "green"
    warning: str = "yellow"
    error: str = "red"
    dim: str = "dim"
    bold: str = "bold"
    text: str = "white"
    background: str = ""


@dataclass
class ThemeStyles:
    """Text styles for terminal output."""

    header: str = "bold cyan"
    subheader: str = "bold blue"
    table_header: str = "bold white on rgb(40,40,40)"
    table_row: str = ""
    table_row_alt: str = "dim"
    link: str = "cyan underline"
    notice_title: str = "bold"
    currency: str = "green"
    confidence_high: str = "green"
    confidence_medium: str = "yellow"
    confidence_low: str = "red"
    finding_risk: str = "bold red"
    caveat: str = "italic yellow"


# Default theme
colors = ThemeColors()
styles = ThemeStyles()


def get_theme() -> tuple[ThemeColors, ThemeStyles]:
    """Get the current theme colors and styles."""
    return colors, styles


def apply_style(text: str, style: str) -> str:
    """Apply a Rich style to text."""
    if not style:
        return text
    return f"[{style}]{text}[/{style}]"


def panelize(title: str, content: str, style: str = "cyan") -> str:
    """Wrap content in a styled panel."""
    return f"[{style}]{title}[/{style}]\n{content}"
