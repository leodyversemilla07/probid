"""Profile and entity lookup CLI commands."""

from __future__ import annotations

import click

from probid_probing_agent.core.data import cache
from probid_probing_agent.core.ui import display


def register_profile_commands(cli: click.Group) -> None:
    """Register supplier and agency profile commands."""

    @cli.command()
    @click.argument("name")
    def supplier(name: str):
        """Look up a supplier's profile and award history."""
        with cache.connection() as conn:
            stats = cache.get_supplier_stats(conn, name)
            display.show_supplier_stats(stats, name)

            awards_list = cache.search_awards(conn, supplier=name, limit=20)
            if awards_list:
                display.show_awards(awards_list, supplier=name)

    @cli.command()
    @click.argument("name")
    def agency(name: str):
        """Show procurement profile for a government agency."""
        with cache.connection() as conn:
            stats = cache.get_agency_stats(conn, name)
            display.show_agency_stats(stats, name)
