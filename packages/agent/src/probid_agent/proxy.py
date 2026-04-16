"""Shared runtime validation and plan-execution helpers for probid agent runtimes."""

from __future__ import annotations

from typing import Any

from probid_agent.errors import PlanValidationError
from probid_agent.types import EventSink, ExecutionPlan, PlanExecutionResult, ToolTraceItem


def validate_plan_contract(plan: ExecutionPlan) -> None:
    steps = plan.get("steps")
    if not steps:
        raise PlanValidationError("Plan must contain at least one step")
    for idx, step in enumerate(steps, start=1):
        if not step.get("tool"):
            raise PlanValidationError(f"Invalid plan step {idx}: missing tool")
        if not step.get("cli_equivalent"):
            raise PlanValidationError(f"Invalid plan step {idx}: missing cli_equivalent")


def execute_plan_steps(
    plan: ExecutionPlan,
    registry: Any,
    *,
    event_sink: EventSink | None = None,
) -> tuple[Any, list[ToolTraceItem]]:
    result = run_plan_execution(plan, registry, event_sink=event_sink)
    return result["payload"], result["tool_trace"]


def run_plan_execution(
    plan: ExecutionPlan,
    registry: Any,
    *,
    event_sink: EventSink | None = None,
) -> PlanExecutionResult:
    payload: Any = None
    tool_trace: list[ToolTraceItem] = []

    for step in plan.get("steps", []):
        payload, trace = registry.execute(
            step.get("tool"),
            step.get("args", {}),
            cli_equivalent=step.get("cli_equivalent", ""),
            event_sink=event_sink,
        )
        tool_trace.append(trace)

    return {"payload": payload, "tool_trace": tool_trace}
