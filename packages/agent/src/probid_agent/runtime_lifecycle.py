"""Reusable runtime lifecycle helpers for session open/restore/persistence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any


def restore_turn_messages(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rebuild in-memory user/assistant message pairs from persisted turn rows."""
    messages: list[dict[str, Any]] = []
    for row in rows:
        if row.get("type") != "turn":
            continue
        user_input = row.get("user_input", "")
        result = row.get("result", {})
        turn_id = row.get("turn_id")
        if user_input:
            messages.append({"role": "user", "content": user_input, "turn_id": turn_id})
        if result:
            messages.append({"role": "assistant", "content": result, "turn_id": turn_id})
    return messages


def open_or_create_session(
    *,
    continue_recent: bool,
    session_manager: Any,
    system_prompt: str,
    session_factory: Callable[..., Any],
) -> Any:
    """Open most recent persisted session or create a fresh one."""
    if continue_recent:
        recent = session_manager.continue_recent()
        if recent is not None:
            session_id, path = recent
            rows = session_manager.read_session_file(path)
            messages = restore_turn_messages(rows)
            session = session_factory(system_prompt=system_prompt, session_id=session_id, messages=messages)
            restore_rows = getattr(session, "restore_from_rows", None)
            if callable(restore_rows):
                restore_rows(rows)
                return session
            restore = getattr(session, "restore_from_messages", None)
            if callable(restore):
                restore()
            return session

    session_id, _path = session_manager.create_session()
    return session_factory(system_prompt=system_prompt, session_id=session_id)


def persist_turn(
    *,
    session_manager: Any,
    session_id: str,
    user_input: str,
    response: dict[str, Any],
) -> None:
    """Persist one completed turn in canonical JSONL format."""
    session_manager.append_turn(
        session_id,
        {
            "type": "turn",
            "turn_id": response.get("turn_id"),
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "user_input": user_input,
            "result": response,
        },
    )
