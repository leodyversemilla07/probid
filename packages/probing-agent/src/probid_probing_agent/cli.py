"""Compatibility wrapper for probid CLI entrypoint."""

from probid_probing_agent.cli import cli

__all__ = ["cli"]


if __name__ == "__main__":
    cli()
