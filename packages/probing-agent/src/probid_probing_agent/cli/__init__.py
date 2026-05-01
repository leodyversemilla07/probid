"""CLI entrypoint and helpers for probid probing agent."""

from __future__ import annotations

from pathlib import Path

import click

from probid_probing_agent.cli.commands import (
    register_agent_commands,
    register_analysis_commands,
    register_award_commands,
    register_export_commands,
    register_profile_commands,
    register_search_commands,
)
from probid_probing_agent.cli.output import resolve_output_text


@click.group(invoke_without_command=True)
@click.version_option("0.1.0", prog_name="probid")
@click.option("-q", "query", help="Run one one-shot harness query and exit")
@click.option(
    "--json-output",
    is_flag=True,
    help="Render the full one-shot result envelope as JSON",
)
@click.option(
    "--export-output",
    is_flag=True,
    help="Render only export content from an export-oriented follow-up; export audit follow-ups stay in the full explain envelope",
)
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(),
    help="Write rendered output to a file instead of stdout",
)
@click.option("--db-path", default=None, help="Override the SQLite cache database path")
@click.option(
    "--provider",
    default="deterministic",
    show_default=True,
    help="Select the harness provider implementation",
)
@click.option(
    "--session-dir",
    default=None,
    help="Override the persisted harness session directory",
)
@click.option(
    "--continue-recent",
    is_flag=True,
    help="Resume the most recent persisted harness session",
)
@click.option(
    "--tui/--no-tui",
    default=True,
    help="Open the interactive TUI instead of the plain REPL",
)
@click.pass_context
def cli(
    ctx: click.Context,
    query: str | None,
    json_output: bool,
    export_output: bool,
    output_path: str | None,
    db_path: str | None,
    provider: str,
    session_dir: str | None,
    continue_recent: bool,
    tui: bool,
):
    """probid — minimal terminal probing agent harness.

    Run local-first, explainable procurement probes from the terminal.
    Supports one-shot investigation queries, session-aware follow-ups,
    export-oriented artifact generation from prior results, and
    export audit follow-ups such as "show last export destination"
    and "list prior exports" against persisted session history.
    Data sourced from PhilGEPS (Philippine Government Electronic Procurement System).
    """
    if query and ctx.invoked_subcommand is not None:
        raise click.UsageError("Cannot use -q/--query together with a subcommand.")

    if query:
        from probid_probing_agent.core.runtime import (
            InvalidProviderError,
            ProbidAgentRuntime,
        )

        try:
            runtime = ProbidAgentRuntime(
                db_path=db_path,
                provider=provider,
                session_dir=session_dir,
                continue_recent=continue_recent,
            )
        except InvalidProviderError as exc:
            raise click.BadParameter(str(exc), param_hint="--provider") from exc
        try:
            result = runtime.handle_input(query)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        output_text = resolve_output_text(
            result=result,
            json_output=json_output,
            export_output=export_output,
            output_path=output_path,
        )

        if output_path:
            Path(output_path).write_text(output_text, encoding="utf-8")
            click.echo(f"Written to {output_path}")
        else:
            click.echo(output_text)
        if export_output:
            runtime.record_export_artifact(result=result, output_text=output_text, output_path=output_path)
        return

    if ctx.invoked_subcommand is None:
        from probid_probing_agent.core.runtime import (
            InvalidProviderError,
            ProbidAgentRuntime,
        )

        try:
            runtime = ProbidAgentRuntime(
                db_path=db_path,
                provider=provider,
                session_dir=session_dir,
                continue_recent=continue_recent,
            )
        except InvalidProviderError as exc:
            raise click.BadParameter(str(exc), param_hint="--provider") from exc

        if tui:
            from probid_probing_agent.modes.interactive.tui_mode import run_interactive

            # Default to internal probid TUI so `probid` always opens the harness UI.
            run_interactive(runtime, model=provider, provider=provider)
        else:
            from probid_probing_agent.modes.interactive.repl import run_agent_repl

            run_agent_repl(runtime)


register_agent_commands(cli)
register_search_commands(cli)
register_award_commands(cli)
register_export_commands(cli)
register_profile_commands(cli)
register_analysis_commands(cli)


__all__ = ["cli"]
