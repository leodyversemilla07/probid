"""CLI entrypoint and helpers for probid probing agent."""

from __future__ import annotations

import json

import click

from probid_probing_agent.cli.commands import (
    register_agent_commands,
    register_analysis_commands,
    register_award_commands,
    register_profile_commands,
    register_search_commands,
)


@click.group(invoke_without_command=True)
@click.version_option("0.1.0", prog_name="probid")
@click.option("-q", "query", help="Run one-shot query mode and exit")
@click.option("--json-output", is_flag=True, help="Emit one-shot query result as JSON")
@click.option("--db-path", default=None, help="Optional SQLite DB path override")
@click.option("--provider", default="deterministic", show_default=True, help="Harness provider implementation")
@click.option("--tui/--no-tui", default=True, help="Use pi-style TUI (default: yes)")
@click.pass_context
def cli(ctx: click.Context, query: str | None, json_output: bool, db_path: str | None, provider: str, tui: bool):
    """probid — minimal terminal probing agent harness.

    Run local-first, explainable procurement probes from the terminal.
    Data sourced from PhilGEPS (Philippine Government Electronic Procurement System).
    """
    if query and ctx.invoked_subcommand is not None:
        raise click.UsageError("Cannot use -q/--query together with a subcommand.")

    if query:
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        try:
            result = ProbidAgentRuntime(db_path=db_path, provider=provider).handle_input(query)
        except ValueError as exc:
            raise click.BadParameter(str(exc), param_hint="--provider") from exc
        if json_output:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            click.echo(result)
        return

    if ctx.invoked_subcommand is None:
        from probid_probing_agent.core.runtime import ProbidAgentRuntime

        try:
            runtime = ProbidAgentRuntime(db_path=db_path, provider=provider)
        except ValueError as exc:
            raise click.BadParameter(str(exc), param_hint="--provider") from exc

        if tui:
            from probid_probing_agent.modes.interactive.tui_mode import run_interactive

            # Default to internal probid TUI so `probid` always opens the harness UI.
            run_interactive(runtime, model="gpt-4", provider=provider)
        else:
            from probid_probing_agent.modes.interactive.repl import run_agent_repl
            run_agent_repl(runtime)


register_agent_commands(cli)
register_search_commands(cli)
register_award_commands(cli)
register_profile_commands(cli)
register_analysis_commands(cli)


__all__ = ["cli"]
