"""Rich-based terminal display for procurement data."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


def format_php(amount: float) -> str:
    """Format a float as Philippine Peso."""
    if amount <= 0:
        return "—"
    if amount >= 1_000_000_000:
        return f"PHP {amount / 1_000_000_000:,.2f}B"
    if amount >= 1_000_000:
        return f"PHP {amount / 1_000_000:,.2f}M"
    if amount >= 1_000:
        return f"PHP {amount / 1_000:,.2f}K"
    return f"PHP {amount:,.2f}"


def show_notices(notices: list[dict], query: str = "") -> None:
    """Display procurement notices in a table."""
    if not notices:
        console.print("[yellow]No results found.[/yellow]")
        return

    title = f"Procurement Notices"
    if query:
        title += f' — "{query}"'

    table = Table(
        title=title,
        box=box.SQUARE,
        show_lines=True,
        title_style="bold cyan",
        header_style="bold white on rgb(40,40,40)",
        row_styles=["", "dim"],
    )

    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Ref No", style="cyan", width=12)
    table.add_column("Published", width=12)
    table.add_column("Closing", width=12)
    table.add_column("Title", max_width=50)
    table.add_column("Category", width=25)
    table.add_column("Area", width=20)

    for i, n in enumerate(notices, 1):
        title_text = n.get("title", "")
        if len(title_text) > 50:
            title_text = title_text[:47] + "..."

        table.add_row(
            str(i),
            n.get("ref_no", ""),
            n.get("posted_date", ""),
            n.get("closing_date", ""),
            title_text,
            n.get("category", "")[:25],
            n.get("area_of_delivery", n.get("agency", ""))[:20],
        )

    console.print(table)
    console.print(f"\n[dim]{len(notices)} result(s)[/dim]")


def show_notice_detail(detail: dict) -> None:
    """Display full notice details."""
    panel_content = []

    fields = [
        ("Ref No", detail.get("ref_no", "")),
        ("Title", detail.get("title", "")),
        ("Agency", detail.get("agency", "")),
        ("Category", detail.get("category", "")),
        ("Area", detail.get("area_of_delivery", "")),
        ("Procurement Mode", detail.get("notice_type", "")),
        ("Classification", detail.get("classification", "")),
        ("Budget", format_php(detail.get("approved_budget", 0))),
        ("Delivery Period", detail.get("delivery_period", "")),
        ("Status", detail.get("status", "")),
        ("Contact", detail.get("contact_person", "")),
    ]

    for label, value in fields:
        if value:
            panel_content.append(f"[bold]{label}:[/bold] {value}")

    if detail.get("description"):
        panel_content.append(f"\n[bold]Description:[/bold]\n{detail['description']}")

    console.print(Panel(
        "\n".join(panel_content),
        title=f"[bold cyan]Notice {detail.get('ref_no', '')}[/bold cyan]",
        box=box.HEAVY,
        border_style="cyan",
    ))


def show_awards(awards: list[dict], agency: str = "", supplier: str = "") -> None:
    """Display contract awards in a table."""
    if not awards:
        console.print("[yellow]No awards found.[/yellow]")
        return

    title = "Recent Contract Awards"
    if agency:
        title += f' — {agency}'
    if supplier:
        title += f' — {supplier}'

    table = Table(
        title=title,
        box=box.SQUARE,
        show_lines=True,
        title_style="bold green",
        header_style="bold white on rgb(40,40,40)",
        row_styles=["", "dim"],
    )

    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Date", width=12)
    table.add_column("Project", max_width=40)
    table.add_column("Supplier", max_width=30)
    table.add_column("Amount", width=15, justify="right")
    table.add_column("Budget", width=15, justify="right")
    table.add_column("Used %", width=8, justify="right")

    for i, a in enumerate(awards, 1):
        amount = a.get("award_amount", 0)
        budget = a.get("approved_budget", 0)
        pct = f"{(amount / budget * 100):.0f}%" if budget > 0 else "—"

        project = a.get("project_title", "")
        if len(project) > 40:
            project = project[:37] + "..."

        supplier_name = a.get("supplier", "")
        if len(supplier_name) > 30:
            supplier_name = supplier_name[:27] + "..."

        table.add_row(
            str(i),
            a.get("award_date", ""),
            project,
            supplier_name,
            format_php(amount),
            format_php(budget),
            pct,
        )

    console.print(table)
    total = sum(a.get("award_amount", 0) for a in awards)
    console.print(f"\n[dim]{len(awards)} award(s) | Total: {format_php(total)}[/dim]")


def show_supplier_stats(stats: dict, supplier: str) -> None:
    """Display supplier profile."""
    lines = [
        f"[bold]Supplier:[/bold] {supplier}",
        f"[bold]Total Awards:[/bold] {stats['total_awards']}",
        f"[bold]Total Value:[/bold] {format_php(stats['total_value'])}",
        f"[bold]Agencies Served:[/bold] {stats['agency_count']}",
    ]

    if stats["agencies"]:
        lines.append(f"\n[bold]Agencies:[/bold]")
        for a in sorted(stats["agencies"]):
            lines.append(f"  - {a}")

    console.print(Panel(
        "\n".join(lines),
        title=f"[bold green]Supplier Profile[/bold green]",
        box=box.HEAVY,
        border_style="green",
    ))


def show_agency_stats(stats: dict, agency: str) -> None:
    """Display agency procurement profile."""
    lines = [
        f"[bold]Agency:[/bold] {agency}",
        f"[bold]Total Awards:[/bold] {stats['total_awards']}",
        f"[bold]Total Spending:[/bold] {format_php(stats['total_spending'])}",
    ]

    if stats["top_suppliers"]:
        lines.append(f"\n[bold]Top Suppliers:[/bold]")
        for s in stats["top_suppliers"]:
            name = s.get("supplier", "Unknown")
            total = format_php(s.get("total", 0))
            count = s.get("cnt", 0)
            lines.append(f"  {count}x {name} — {total}")

    console.print(Panel(
        "\n".join(lines),
        title=f"[bold magenta]Agency Profile[/bold magenta]",
        box=box.HEAVY,
        border_style="magenta",
    ))


def show_repeat_awardees(awardees: list[dict]) -> None:
    """Display suppliers with high award frequency."""
    if not awardees:
        console.print("[yellow]No repeat awardees found above threshold.[/yellow]")
        return

    table = Table(
        title="Repeat Awardees (Potential Red Flags)",
        box=box.SQUARE,
        show_lines=True,
        title_style="bold red",
        header_style="bold white on rgb(80,20,20)",
        row_styles=["", "dim"],
    )

    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Supplier", max_width=35)
    table.add_column("Awards", width=8, justify="right")
    table.add_column("Agencies", width=10, justify="right")
    table.add_column("Total Value", width=15, justify="right")
    table.add_column("Avg per Award", width=15, justify="right")

    for i, a in enumerate(awardees, 1):
        count = a.get("award_count", 0)
        total = a.get("total_value", 0) or 0
        avg = total / count if count > 0 else 0

        name = a.get("supplier", "")
        if len(name) > 35:
            name = name[:32] + "..."

        table.add_row(
            str(i),
            name,
            str(count),
            str(a.get("agency_count", 0)),
            format_php(total),
            format_php(avg),
        )

    console.print(table)


def show_overprice_analysis(results: list[dict], threshold: int = 200) -> None:
    """Display overpricing analysis results."""
    if not results:
        console.print("[yellow]No price anomalies detected.[/yellow]")
        return

    table = Table(
        title="Overpricing Analysis",
        box=box.SQUARE,
        show_lines=True,
        title_style="bold yellow",
        header_style="bold white on rgb(80,80,0)",
        row_styles=["", "dim"],
    )

    table.add_column("#", width=4, justify="right")
    table.add_column("Category", max_width=30)
    table.add_column("Low", width=15, justify="right")
    table.add_column("High", width=15, justify="right")
    table.add_column("Spread", width=10, justify="right")
    table.add_column("Flag", width=6, justify="center")
    table.add_column("Samples", width=8, justify="right")

    for i, r in enumerate(results, 1):
        low = r.get("min_price", 0)
        high = r.get("max_price", 0)
        spread = ((high - low) / low * 100) if low > 0 else 0
        flag = "[red]![/red]" if spread > threshold else ""
        count = r.get("sample_count", 0)

        table.add_row(
            str(i),
            r.get("category", "")[:30],
            format_php(low),
            format_php(high),
            f"{spread:.0f}%",
            flag,
            str(count),
        )

    console.print(table)


def show_network(result: dict, supplier_name: str) -> None:
    """Display supplier network analysis."""
    if not result.get("agencies_served"):
        error(f"No data found for supplier: {supplier_name}")
        return

    lines = [f"[bold]Supplier:[/bold] {supplier_name}"]
    lines.append(f"[bold]Agencies served:[/bold] {len(result['agencies_served'])}")
    for a in sorted(result["agencies_served"]):
        lines.append(f"  - {a}")

    if result.get("competitors"):
        lines.append(f"\n[bold]Competitors (shared agencies):[/bold]")
        for c in result["competitors"][:10]:
            lines.append(f"  {c['supplier']} — {c['shared_agencies']} shared agencies")

    console.print(Panel(
        "\n".join(lines),
        title="[bold cyan]Supplier Network[/bold cyan]",
        box=box.HEAVY,
        border_style="cyan",
    ))


def show_agencies_list(agency_list: list[dict]) -> None:
    """Display agency rows from the View By Agency page."""
    if not agency_list:
        error("No agencies found (site may be blocking)")
        return

    table = Table(
        title="PhilGEPS Agencies",
        box=box.SQUARE,
        show_lines=True,
        title_style="bold cyan",
        header_style="bold white on rgb(40,40,40)",
        row_styles=["", "dim"],
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Agency", style="cyan", min_width=40)
    table.add_column("Open Opportunities", width=18, justify="right")

    for agency in agency_list:
        table.add_row(
            str(agency.get("rank", "")),
            agency.get("name", ""),
            str(agency.get("opportunity_count", 0)),
        )

    console.print(table)
    success(f"{len(agency_list)} agencies found")


def show_split_contracts(results: list[dict], agency: str) -> None:
    """Display contract splitting detection results."""
    if not results:
        info(f"No split contract patterns detected for {agency}")
        return

    for r in results:
        lines = [
            f"[bold red]Pattern:[/bold red] {r['pattern']}",
            f"[bold]Total value:[/bold] {format_php(r['total_value'])}",
            f"[bold]Contracts:[/bold]",
        ]
        for c in r["contracts"]:
            date = c.get('award_date', '')
            amount = format_php(c.get('award_amount', 0))
            title = c.get('project_title', '')[:60]
            lines.append(f"  {date} — {amount} — {title}")

        console.print(Panel(
            "\n".join(lines),
            title="[bold red]Split Contract Alert[/bold red]",
            box=box.HEAVY,
            border_style="red",
        ))


def info(msg: str) -> None:
    """Print an info message."""
    console.print(f"[cyan]>[/cyan] {msg}")


def error(msg: str) -> None:
    """Print an error message."""
    console.print(f"[red]Error:[/red] {msg}")


def success(msg: str) -> None:
    """Print a success message."""
    console.print(f"[green]OK[/green] {msg}")
