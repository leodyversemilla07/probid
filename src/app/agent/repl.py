"""Minimal terminal REPL for probid agent."""

from __future__ import annotations

import json

import click

from app.agent.runtime import ProbidAgentRuntime
from app.ui import display


def _print_help() -> None:
    click.echo("Commands: /help, /json, /why, /prompt, /tools, /mode, /reset, /exit")


def run_agent_repl(runtime: ProbidAgentRuntime) -> None:
    click.echo("probid (minimal + agentive) — type /help for commands")
    json_mode = False
    why_mode = False

    while True:
        try:
            user_input = click.prompt("agent", prompt_suffix="> ")
        except (EOFError, KeyboardInterrupt):
            click.echo("\nBye.")
            return

        cmd = user_input.strip().lower()
        if cmd in {"/exit", "/quit"}:
            click.echo("Bye.")
            return
        if cmd == "/help":
            _print_help()
            continue
        if cmd == "/json":
            json_mode = not json_mode
            click.echo(f"json_mode={json_mode}")
            continue
        if cmd == "/why":
            why_mode = not why_mode
            click.echo(f"why_mode={why_mode}")
            continue
        if cmd == "/prompt":
            click.echo(runtime.system_prompt)
            continue
        if cmd == "/tools":
            click.echo("CLI-parity tools:")
            for tool_cmd in runtime.available_tools():
                click.echo(f"  - {tool_cmd}")
            continue
        if cmd == "/mode":
            click.echo(
                f"mode=interactive json_mode={json_mode} why_mode={why_mode} cache_only={runtime.default_cache_only}"
            )
            continue
        if cmd == "/reset":
            click.echo("Session reset (runtime stateless; logs continue).")
            continue
        if not user_input.strip():
            continue

        result = runtime.handle_input(user_input)

        if json_mode:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
            continue

        display.info(f"Intent: {result.get('intent')} | Query: {result.get('query')}")
        if result.get("evidence"):
            display.info("Evidence: " + " | ".join(result["evidence"]))

        findings = result.get("findings", [])
        if findings:
            for idx, finding in enumerate(findings[:5], 1):
                if isinstance(finding, dict):
                    code = finding.get("reason_code", "")
                    summary = finding.get("summary", str(finding))
                    prefix = f"[{code}] " if code else ""
                    display.success(f"{idx}. {prefix}{summary}")
                else:
                    display.success(f"{idx}. {finding}")
        else:
            display.info("No findings.")

        if why_mode and result.get("caveats"):
            for caveat in result["caveats"]:
                display.info(f"Caveat: {caveat}")

        if result.get("next_actions"):
            display.info("Next actions:")
            for action in result["next_actions"][:5]:
                click.echo(f"  - {action}")

        if result.get("turn_id"):
            display.info(f"Turn ID: {result['turn_id']}")
