"""Reusable session-state primitives for probid agent core."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from probid_agent.types import EventListener, SessionStateSnapshot


class BaseAgentSession:
    def __init__(
        self,
        system_prompt: str,
        session_id: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        steering_mode: Literal["all", "one-at-a-time"] = "one-at-a-time",
        follow_up_mode: Literal["all", "one-at-a-time"] = "one-at-a-time",
    ):
        self.session_id = session_id or uuid4().hex
        self.system_prompt = system_prompt
        self.messages: list[dict[str, Any]] = list(messages or [])
        self.tool_trace: list[dict[str, Any]] = []
        self.is_streaming = False
        self.steering_mode = steering_mode
        self.follow_up_mode = follow_up_mode
        self.queued_steering: list[str] = []
        self.queued_follow_up: list[str] = []
        self._listeners: list[EventListener] = []

    def subscribe(self, listener: EventListener):
        self._listeners.append(listener)

        def _unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _unsubscribe

    def _emit(self, event: dict[str, Any]) -> None:
        for listener in list(self._listeners):
            listener(event)

    def snapshot_state(self) -> SessionStateSnapshot:
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "tool_trace_count": len(self.tool_trace),
            "is_streaming": self.is_streaming,
            "queued_steering": len(self.queued_steering),
            "queued_follow_up": len(self.queued_follow_up),
        }

    def _emit_queue_update(self) -> None:
        self._emit(
            {
                "type": "queue_update",
                "steering": list(self.queued_steering),
                "follow_up": list(self.queued_follow_up),
            }
        )

    def steer(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.queued_steering.append(text)
        self._emit_queue_update()

    def follow_up(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.queued_follow_up.append(text)
        self._emit_queue_update()

    def clear_steering_queue(self) -> None:
        self.queued_steering.clear()
        self._emit_queue_update()

    def clear_follow_up_queue(self) -> None:
        self.queued_follow_up.clear()
        self._emit_queue_update()

    def clear_all_queues(self) -> None:
        self.queued_steering.clear()
        self.queued_follow_up.clear()
        self._emit_queue_update()

    def has_queued_messages(self) -> bool:
        return bool(self.queued_steering or self.queued_follow_up)

    def _drain_steering(self) -> list[str]:
        return self._drain_queue(self.queued_steering, self.steering_mode)

    def _drain_follow_up(self) -> list[str]:
        return self._drain_queue(self.queued_follow_up, self.follow_up_mode)

    def _drain_queue(self, queue: list[str], mode: Literal["all", "one-at-a-time"]) -> list[str]:
        if not queue:
            return []
        if mode == "all":
            drained = list(queue)
            queue.clear()
            return drained
        return [queue.pop(0)]

    def new_turn_id(self) -> str:
        return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
