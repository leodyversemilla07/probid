"""Built-in providers for probid agent runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.data import cache

from app.agent.planner import plan_for_input
from app.agent.provider_registry import Provider, register_provider
from app.agent.tools import AgentToolAdapter

if TYPE_CHECKING:
    from app.agent.runtime import ProbidAgentRuntime


def _validate_plan(runtime: "ProbidAgentRuntime", plan: dict[str, Any]) -> None:
    runtime._validate_plan(plan)


def _run_plan(runtime: "ProbidAgentRuntime", plan: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    tool_trace: list[dict[str, Any]] = []

    with cache.connection(db_path=runtime.db_path) as conn:
        adapter = AgentToolAdapter(conn)
        payload: Any = None

        for step in plan.get("steps", []):
            tool_name = step.get("tool")
            args = step.get("args", {})
            fn = getattr(adapter, tool_name)
            payload = fn(**args)
            tool_trace.append(
                {
                    "tool": tool_name,
                    "args": args,
                    "cli_equivalent": step.get("cli_equivalent", ""),
                    "result_type": type(payload).__name__,
                }
            )

    return payload, tool_trace


def handle_deterministic(user_input: str, runtime: "ProbidAgentRuntime") -> dict[str, Any]:
    plan = plan_for_input(user_input)
    _validate_plan(runtime, plan)

    payload, tool_trace = _run_plan(runtime, plan)
    return runtime._compose_response(plan=plan, payload=payload, tool_trace=tool_trace)


def register_builtins() -> None:
    register_provider(
        Provider(name="deterministic", handle=handle_deterministic),
        source_id="builtin",
    )


register_builtins()
