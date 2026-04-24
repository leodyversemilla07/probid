"""Agent harness command registration."""

from __future__ import annotations

from pathlib import Path

import click

from probid_probing_agent.cli.output import resolve_output_text
from probid_probing_agent.core.runtime import InvalidProviderError, ProbidAgentRuntime
from probid_probing_agent.modes.interactive.repl import run_agent_repl


def register_agent_commands(cli: click.Group) -> None:
    """Register minimal terminal probing agent harness command."""

    @cli.command()
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
    def agent(
        query: str | None,
        json_output: bool,
        export_output: bool,
        output_path: str | None,
        db_path: str | None,
        provider: str,
        session_dir: str | None,
        continue_recent: bool,
    ):
        """Run the explicit probid agent harness command.

        This mirrors the root harness behavior while providing an explicit
        subcommand entrypoint for one-shot queries and interactive sessions,
        including session-aware export audit prompts like "show last export destination"
        and "list prior exports".
        """
        try:
            runtime = ProbidAgentRuntime(
                db_path=db_path,
                provider=provider,
                session_dir=session_dir,
                continue_recent=continue_recent,
            )
        except InvalidProviderError as exc:
            raise click.BadParameter(str(exc), param_hint="--provider") from exc
        if query:
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
        run_agent_repl(runtime)
