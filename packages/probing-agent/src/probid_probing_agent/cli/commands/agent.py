"""Agent harness command registration."""

from __future__ import annotations

import json

import click

from probid_probing_agent.modes.interactive.repl import run_agent_repl
from probid_probing_agent.core.runtime import ProbidAgentRuntime


def register_agent_commands(cli: click.Group) -> None:
    """Register minimal terminal probing agent harness command."""

    @cli.command()
    @click.option("-q", "query", help="Run one-shot query mode and exit")
    @click.option("--json-output", is_flag=True, help="Emit one-shot query result as JSON")
    @click.option("--db-path", default=None, help="Optional SQLite DB path override")
    @click.option("--provider", default="deterministic", show_default=True, help="Harness provider implementation")
    def agent(query: str | None, json_output: bool, db_path: str | None, provider: str):
        """Run minimal terminal probing agent harness."""
        try:
            runtime = ProbidAgentRuntime(db_path=db_path, provider=provider)
        except ValueError as exc:
            raise click.BadParameter(str(exc), param_hint="--provider") from exc
        if query:
            result = runtime.handle_input(query)
            if json_output:
                click.echo(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                click.echo(result)
            return
        run_agent_repl(runtime)
