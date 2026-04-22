"""Shared runtime types for probid agent core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypedDict, runtime_checkable


class QueueUpdateEvent(TypedDict):
    type: str
    steering: list[str]
    follow_up: list[str]


class TurnStartEvent(TypedDict):
    type: str
    turn_id: str
    user_input: str
    queued_steering: list[str]
    queued_follow_up: list[str]


class TurnEndEvent(TypedDict):
    type: str
    turn_id: str
    response: dict[str, Any]
    tool_trace: list[dict[str, Any]]


class ToolExecutionEvent(TypedDict, total=False):
    type: str
    tool: str
    args: dict[str, Any]
    cli_equivalent: str
    status: str
    result_type: str
    error: str


AgentEvent = QueueUpdateEvent | TurnStartEvent | TurnEndEvent | ToolExecutionEvent | dict[str, Any]

EventListener = Callable[[AgentEvent], None]
EventSink = Callable[[AgentEvent], None]
ToolHandler = Callable[..., Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: tuple[str, ...]
    handler: ToolHandler


class SessionStateSnapshot(TypedDict):
    session_id: str
    message_count: int
    tool_trace_count: int
    is_streaming: bool
    queued_steering: int
    queued_follow_up: int


class PlanStep(TypedDict, total=False):
    tool: str
    args: dict[str, Any]
    cli_equivalent: str


class ExecutionPlan(TypedDict, total=False):
    intent: str
    query: str
    steps: list[PlanStep]


class ToolTraceItem(TypedDict, total=False):
    tool: str
    description: str
    args: dict[str, Any]
    cli_equivalent: str
    status: str
    result_type: str
    error: str
    payload: Any


class PlanExecutionResult(TypedDict):
    payload: Any
    tool_trace: list[ToolTraceItem]


class ResponseEnvelope(TypedDict):
    intent: str
    query: str
    assumptions: list[str]
    evidence: list[str]
    findings: list[dict[str, Any]]
    caveats: list[str]
    next_actions: list[str]
    tool_trace: list[ToolTraceItem]


@runtime_checkable
class SessionProtocol(Protocol):
    session_id: str
    messages: list[dict[str, Any]]
    tool_trace: list[dict[str, Any]]
    is_streaming: bool
    queued_steering: list[str]
    queued_follow_up: list[str]

    def subscribe(self, listener: EventListener): ...

    def snapshot_state(self) -> SessionStateSnapshot: ...

    def steer(self, text: str) -> None: ...

    def follow_up(self, text: str) -> None: ...

    def clear_steering_queue(self) -> None: ...

    def clear_follow_up_queue(self) -> None: ...

    def clear_all_queues(self) -> None: ...

    def has_queued_messages(self) -> bool: ...

    def prompt(self, user_input: str, runtime: Any) -> dict[str, Any]: ...


@runtime_checkable
class ProviderRuntimeProtocol(Protocol):
    db_path: str | None
    session: SessionProtocol

    def _validate_plan(self, plan: ExecutionPlan) -> None: ...

    def _compose_response(
        self,
        plan: ExecutionPlan,
        payload: Any,
        tool_trace: list[ToolTraceItem],
    ) -> ResponseEnvelope: ...


@runtime_checkable
class RuntimeStateProtocol(Protocol):
    db_path: str | None
    provider_name: str
    provider: Any
    session: SessionProtocol

    def new_session(self) -> SessionProtocol: ...

    def handle_input(self, user_input: str) -> dict[str, Any]: ...


class DomainResponsePolicy(Protocol):
    def assumptions(self) -> list[str]: ...

    def enrich(self, envelope: ResponseEnvelope, context: dict[str, Any]) -> None: ...
