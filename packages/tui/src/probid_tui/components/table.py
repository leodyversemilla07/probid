"""Core TUI components for probid."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def format_currency(amount: float, currency: str = "PHP") -> str:
    """Format a numeric amount as currency."""
    if amount <= 0:
        return "—"
    if amount >= 1_000_000_000:
        return f"{currency} {amount / 1_000_000_000:,.2f}B"
    if amount >= 1_000_000:
        return f"{currency} {amount / 1_000_000:,.2f}M"
    if amount >= 1_000:
        return f"{currency} {amount / 1_000:,.2f}K"
    return f"{currency} {amount:,.2f}"


def format_table_row(index: int, columns: list[str], column_widths: list[int] | None = None) -> list[str]:
    """Format a table row with proper alignment."""
    if column_widths:
        return [col.ljust(width) for col, width in zip(columns, column_widths, strict=False)]
    return columns


def create_table(
    title: str | None = None,
    columns: Sequence[str] = (),
    column_styles: Sequence[str] = (),
    show_lines: bool = False,
) -> Table:
    """Create a Rich table with standard configuration."""
    table = Table(
        title=title,
        show_lines=show_lines,
        box=box.SQUARE if show_lines else box.SIMPLE,
    )

    for col, style in zip(columns, column_styles, strict=False):
        table.add_column(col, style=style or "")

    return table


def create_panel(
    content: str | Text,
    title: str | None = None,
    style: str = "cyan",
    expand: bool = True,
) -> Panel:
    """Create a Rich panel with standard configuration."""
    return Panel(
        content,
        title=title,
        style=style,
        expand=expand,
        border_style=style,
    )


def print_header(text: str, style: str = "bold cyan") -> None:
    """Print a section header."""
    console.print(f"\n[{style}]{text}[/{style}]\n")


def print_subheader(text: str, style: str = "bold blue") -> None:
    """Print a subsection header."""
    console.print(f"[{style}]{text}[/{style}]")


def print_success(text: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {text}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow] {text}")


def print_error(text: str) -> None:
    """Print an error message."""
    console.print(f"[red]✗[/red] {text}")


def print_info(text: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {text}")


@dataclass
class TableConfig:
    """Configuration for a data table."""

    title: str | None = None
    columns: tuple[str, ...] = ()
    column_styles: tuple[str, ...] = ()
    show_lines: bool = False
    max_width: int | None = None


def render_table_data(
    rows: list[list[str]],
    config: TableConfig,
) -> Table:
    """Render a table from row data."""
    table = create_table(
        title=config.title,
        columns=config.columns,
        column_styles=config.column_styles,
        show_lines=config.show_lines,
    )

    for row in rows:
        table.add_row(*row)

    return table
