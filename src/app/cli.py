"""probid CLI — Probe Philippine government procurement."""

from __future__ import annotations

import click

from app.commands import (
    register_analysis_commands,
    register_award_commands,
    register_profile_commands,
    register_search_commands,
)


@click.group()
@click.version_option("0.1.0", prog_name="probid")
def cli():
    """probid — Probe Philippine government procurement.

    Search procurement notices, track contract awards, and detect suspicious patterns.
    Data sourced from PhilGEPS (Philippine Government Electronic Procurement System).
    """
    pass


register_search_commands(cli)
register_award_commands(cli)
register_profile_commands(cli)
register_analysis_commands(cli)


if __name__ == "__main__":
    cli()
