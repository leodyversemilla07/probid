"""Analysis and anomaly detection CLI commands."""

from __future__ import annotations

import click

from app import analysis
from app.data import cache
from app.ui import display


def register_analysis_commands(cli: click.Group) -> None:
    """Register analysis commands."""

    @cli.command()
    @click.argument("category", default="")
    @click.option("--threshold", "-t", default=200, help="Price spread %% to flag")
    def overprice(category: str, threshold: int):
        """Detect pricing anomalies across agencies.

        Compare similar items to find potential overpricing.
        CATEGORY can be partial (e.g., "laptop", "consulting").
        """
        with cache.connection() as conn:
            results = analysis.find_price_anomalies(conn, category=category)
            display.show_overprice_analysis(results, threshold=threshold)

    @cli.command()
    @click.option("--min-count", "-n", default=3, help="Minimum award count to flag")
    def repeat(min_count: int):
        """Find suppliers with high award frequency (potential red flags)."""
        with cache.connection() as conn:
            awardees = analysis.find_repeat_awardees(conn, min_count=min_count)
            display.show_repeat_awardees(awardees)

    @cli.command()
    @click.argument("supplier_name")
    def network(supplier_name: str):
        """Analyze a supplier's network — agencies, competitors."""
        with cache.connection() as conn:
            display.info(f"Analyzing network for {supplier_name}...")
            result = analysis.network_analysis(conn, supplier_name)
            display.show_network(result, supplier_name)

    @cli.command()
    @click.argument("agency")
    @click.option("--gap-days", default=30, help="Max days between related contracts")
    def split(agency: str, gap_days: int):
        """Detect potential contract splitting for an agency."""
        with cache.connection() as conn:
            results = analysis.detect_split_contracts(conn, agency, gap_days)
            display.show_split_contracts(results, agency)
