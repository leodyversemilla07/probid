"""Export artifact inspection commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from probid_probing_agent.core.session_manager import ProbidSessionManager


def _resolve_session_id(manager: ProbidSessionManager, session_id: str | None) -> str:
    if not session_id:
        recent = manager.continue_recent()
        if recent is None:
            raise click.UsageError("No persisted sessions found. Run a session-aware export first.")
        resolved_session_id, _path = recent
        return resolved_session_id

    sessions = manager.list_sessions()
    exact = [item for item in sessions if item["session_id"] == session_id]
    if exact:
        return exact[0]["session_id"]
    prefix = [item for item in sessions if str(item["session_id"]).startswith(session_id)]
    if len(prefix) == 1:
        return prefix[0]["session_id"]
    if len(prefix) > 1:
        raise click.UsageError(f"Session id prefix '{session_id}' is ambiguous.")
    raise click.UsageError(f"Session '{session_id}' was not found.")


def _format_artifact_row(artifact: dict, include_session: bool = False, session_id: str | None = None) -> str:
    artifact_format = artifact.get("export_format", "unknown")
    destination = artifact.get("output_path") or artifact.get("destination", "stdout")
    query = artifact.get("query", "")
    line = f"- {artifact_format}: {destination} (query: {query})"
    if include_session and session_id:
        line = f"[{session_id[:8]}...] {line}"
    return line


def _artifact_sort_key(artifact: dict) -> tuple[str, str]:
    timestamp = str(artifact.get("timestamp", ""))
    turn_id = str(artifact.get("origin_turn_id", ""))
    return (timestamp, turn_id)


def _collect_all_artifacts(manager: ProbidSessionManager, export_format: str | None, limit: int | None) -> list[tuple[str, dict]]:
    sessions = manager.list_sessions()
    all_artifacts = []
    for sess in sessions:
        sess_id = sess["session_id"]
        rows = manager.read_session(sess_id)
        artifacts = [row for row in rows if row.get("type") == "export_artifact"]
        if export_format:
            normalized_format = export_format.strip().lower()
            artifacts = [row for row in artifacts if str(row.get("export_format", "")).strip().lower() == normalized_format]
        artifacts.sort(key=_artifact_sort_key, reverse=True)
        for artifact in artifacts:
            all_artifacts.append((sess_id, artifact))
    all_artifacts.sort(key=lambda x: _artifact_sort_key(x[1]), reverse=True)
    if limit:
        all_artifacts = all_artifacts[:limit]
    return all_artifacts


def register_export_commands(cli: click.Group) -> None:
    @cli.command("exports")
    @click.option("--session-dir", default=None, help="Override the persisted harness session directory")
    @click.option("--session-id", default=None, help="Inspect a specific persisted session id or unique prefix")
    @click.option("--format", "export_format", default=None, help="Filter export artifacts by format (json, markdown, csv, timeline, findings_table, handoff, case_summary)")
    @click.option("--json", "json_output", is_flag=True, help="Render export artifact rows as JSON")
    @click.option("--all", "all_sessions", is_flag=True, help="List export artifacts across all sessions")
    @click.option("--limit", "limit", default=None, type=int, help="Limit number of artifacts to show (per session if not using --all)")
    def exports(session_dir: str | None, session_id: str | None, export_format: str | None, json_output: bool, all_sessions: bool, limit: int | None) -> None:
        """List persisted export artifacts.

        Defaults to the most recent session when neither --session-id nor --all is provided.
        Use --all to list exports across all sessions.
        """
        manager = ProbidSessionManager(Path(session_dir) if session_dir else None)

        # Handle --all flag: collect from all sessions
        if all_sessions:
            artifacts_with_sessions = _collect_all_artifacts(manager, export_format, limit)
            if json_output:
                # For JSON, group by session
                grouped = {}
                for sess_id, artifact in artifacts_with_sessions:
                    if sess_id not in grouped:
                        grouped[sess_id] = []
                    grouped[sess_id].append(artifact)
                click.echo(
                    json.dumps(
                        {"format": export_format, "limit": limit, "sessions": grouped},
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                return
            if not artifacts_with_sessions:
                format_note = f" with format '{export_format}'" if export_format else ""
                click.echo(f"No export artifacts found across sessions{format_note}.")
                return
            heading = "Export artifacts across all sessions"
            if export_format:
                heading += f" (format={export_format})"
            if limit:
                heading += f" (limit={limit})"
            click.echo(heading + ":")
            for sess_id, artifact in artifacts_with_sessions:
                click.echo(_format_artifact_row(artifact, include_session=True, session_id=sess_id))
            return

        # Default: single session mode
        selected_session_id = _resolve_session_id(manager, session_id)
        rows = manager.read_session(selected_session_id)
        artifacts = [row for row in rows if row.get("type") == "export_artifact"]
        if export_format:
            normalized_format = export_format.strip().lower()
            artifacts = [row for row in artifacts if str(row.get("export_format", "")).strip().lower() == normalized_format]
        artifacts.sort(key=_artifact_sort_key, reverse=True)
        if limit:
            artifacts = artifacts[:limit]

        if json_output:
            click.echo(
                json.dumps(
                    {"session_id": selected_session_id, "format": export_format, "limit": limit, "exports": artifacts},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return
        if not artifacts:
            format_note = f" with format '{export_format}'" if export_format else ""
            click.echo(f"No export artifacts found for session {selected_session_id}{format_note}.")
            return

        heading = f"Export artifacts for session {selected_session_id}"
        if export_format:
            heading += f" (format={export_format})"
        if limit:
            heading += f" (limit={limit})"
        click.echo(heading + ":")
        for artifact in artifacts:
            click.echo(_format_artifact_row(artifact))
