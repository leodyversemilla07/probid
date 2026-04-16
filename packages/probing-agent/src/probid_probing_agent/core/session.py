"""Session state and logging for the probid probing agent harness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from probid_agent.agent_loop import BaseAgentSession
from probid_agent.session_logger import JsonlTurnLogger


class ProbidAgentSession(BaseAgentSession):
    """Minimal in-memory session state for the probing harness.

    This is intentionally small: it tracks message history, turn IDs, tool traces,
    queue placeholders, and lightweight event subscribers so the runtime can evolve
    toward fuller tool-calling/state-management behavior without a rewrite.
    """

    def prompt(self, user_input: str, runtime: Any) -> dict[str, Any]:
        turn_id = self.new_turn_id()
        steering = self._drain_steering()
        follow_up = self._drain_follow_up()
        self._emit_queue_update()

        effective_input = user_input
        if steering:
            effective_input = user_input + "\n\n[Queued steering]\n" + "\n".join(f"- {item}" for item in steering)
        if follow_up:
            effective_input = effective_input + "\n\n[Queued follow-up]\n" + "\n".join(
                f"- {item}" for item in follow_up
            )

        self.is_streaming = True
        self.messages.append({"role": "user", "content": user_input, "turn_id": turn_id})
        self._emit(
            {
                "type": "turn_start",
                "turn_id": turn_id,
                "user_input": user_input,
                "queued_steering": steering,
                "queued_follow_up": follow_up,
            }
        )

        try:
            response = runtime.provider.handle(effective_input, runtime)
        finally:
            self.is_streaming = False

        self.tool_trace = list(response.get("tool_trace", []))
        self.messages.append(
            {
                "role": "assistant",
                "content": response,
                "turn_id": turn_id,
            }
        )
        response["turn_id"] = turn_id
        response["session_id"] = self.session_id
        response["state"] = self.snapshot_state()
        response["queue_applied"] = {
            "steering": steering,
            "follow_up": follow_up,
        }
        self._emit(
            {
                "type": "turn_end",
                "turn_id": turn_id,
                "response": response,
                "tool_trace": self.tool_trace,
            }
        )
        return response


class AgentSessionLogger(JsonlTurnLogger):
    def __init__(self, path: Path | None = None):
        super().__init__(path or (Path.home() / ".probid" / "agent-sessions.jsonl"))
