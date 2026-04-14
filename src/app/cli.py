"""probid CLI — Probe Philippine government procurement."""

from __future__ import annotations

import json

import click

from app.commands import (
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
@click.option("--provider", default="deterministic", show_default=True, help="Agent provider implementation")
@click.pass_context
def cli(ctx: click.Context, query: str | None, json_output: bool, db_path: str | None, provider: str):
    """probid — Probe Philippine government procurement.

    Search procurement notices, track contract awards, and detect suspicious patterns.
    Data sourced from PhilGEPS (Philippine Government Electronic Procurement System).
    """
    if query and ctx.invoked_subcommand is not None:
        raise click.UsageError("Cannot use -q/--query together with a subcommand.")

    if query:
        from app.agent.runtime import ProbidAgentRuntime

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
        from app.agent.repl import run_agent_repl
        from app.agent.runtime import ProbidAgentRuntime

        try:
            runtime = ProbidAgentRuntime(db_path=db_path, provider=provider)
        except ValueError as exc:
            raise click.BadParameter(str(exc), param_hint="--provider") from exc
        run_agent_repl(runtime)


register_agent_commands(cli)
register_search_commands(cli)
register_award_commands(cli)
register_profile_commands(cli)
register_analysis_commands(cli)


if __name__ == "__main__":
    cli()
