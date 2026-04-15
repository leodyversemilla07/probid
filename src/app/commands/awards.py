"""Award-related CLI commands."""

from __future__ import annotations

import click

from app.data import cache
from app.sources import philgeps as geps
from app.ui import display


def register_award_commands(cli: click.Group) -> None:
    """Register award commands."""

    @cli.command()
    @click.option("--agency", "-a", help="Filter by agency name")
    @click.option("--supplier", "-s", help="Filter by supplier name")
    @click.option("--limit", "-n", default=50, help="Max results")
    @click.option("--pages", "-p", default=1, help="Award result pages to fetch")
    @click.option("--cache-only", is_flag=True, help="Only search local cache")
    def awards(agency: str, supplier: str, limit: int, pages: int, cache_only: bool):
        """List recent contract awards."""
        with cache.connection() as conn:
            if not cache_only and not supplier:
                display.info("Fetching recent awards from PhilGEPS...")
                try:
                    geps_awards = geps.search_awards(agency=agency, max_pages=max(1, pages))
                    for award in geps_awards:
                        cache.upsert_award(conn, award)
                except Exception as e:
                    display.error(f"Scraping failed: {e}")

            results = cache.search_awards(
                conn,
                agency=agency,
                supplier=supplier,
                limit=limit,
            )
            display.show_awards(results, agency=agency, supplier=supplier)

            if not cache_only:
                try:
                    geps.close()
                except Exception:
                    pass
