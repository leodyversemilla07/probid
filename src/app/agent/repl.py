"""Minimal terminal REPL for probid agent."""

from __future__ import annotations

import json

import click

from app.agent.auth import AgentAuthStore
from app.agent.runtime import ProbidAgentRuntime
from app.ui import display


def _print_help() -> None:
    click.echo("Commands: /help, /json, /why, /prompt, /tools, /mode, /login, /logout, /reset, /exit")


def run_agent_repl(runtime: ProbidAgentRuntime) -> None:
    click.echo("probid (minimal + agentive) — type /help for commands")
    json_mode = False
    why_mode = False
    auth_store = AgentAuthStore()

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
        if cmd.startswith("/login"):
            parts = user_input.strip().split(maxsplit=2)
            if len(parts) < 3:
                click.echo("Usage: /login <provider> <token>")
                continue
            provider, token = parts[1], parts[2]
            normalized_provider = auth_store.login(provider=provider, token=token)
            if normalized_provider == "github-copilot":
                click.echo("Logged in: provider=github-copilot (token saved in local auth store)")
            else:
                click.echo(f"Logged in: provider={normalized_provider}")
            continue
        if cmd.startswith("/logout"):
            parts = user_input.strip().split(maxsplit=1)
            provider = parts[1] if len(parts) > 1 else None
            removed, normalized_provider = auth_store.logout(provider=provider)
            if provider:
                if removed:
                    click.echo(f"Logged out: provider={normalized_provider}")
                else:
                    click.echo(f"No active login found for provider={normalized_provider}")
            else:
                click.echo("Logged out all providers." if removed else "No active logins.")
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
