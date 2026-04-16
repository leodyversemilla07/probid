"""Built-in providers for probid agent runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from probid_agent.provider_runner import DeterministicProviderAdapter
from probid_agent.proxy import execute_plan_steps
from probid_probing_agent.core.data import cache

from probid_probing_agent.core.planner import plan_for_input
from probid_probing_agent.core.provider_registry import Provider, register_provider
from probid_probing_agent.core.tools import build_tool_registry

from probid_probing_agent.core.providers_ai import handle_ai

if TYPE_CHECKING:
    from probid_agent.types import ExecutionPlan, ProviderRuntimeProtocol, ToolTraceItem


def _validate_plan(runtime: "ProviderRuntimeProtocol", plan: "ExecutionPlan") -> None:
    runtime._validate_plan(plan)


def _run_plan(runtime: "ProviderRuntimeProtocol", plan: "ExecutionPlan") -> tuple[Any, list["ToolTraceItem"]]:
    with cache.connection(db_path=runtime.db_path) as conn:
        registry = build_tool_registry(conn)
        return execute_plan_steps(plan, registry, event_sink=runtime.session._emit)


_deterministic = DeterministicProviderAdapter(
    build_plan=plan_for_input,
    execute_plan=_run_plan,
)


def handle_deterministic(user_input: str, runtime: "ProviderRuntimeProtocol") -> dict[str, Any]:
    return _deterministic.handle(user_input, runtime)


def register_builtins() -> None:
    register_provider(
        Provider(name="deterministic", handle=handle_deterministic),
        source_id="builtin",
    )
    register_provider(
        Provider(name="ai", handle=handle_ai),
        source_id="builtin",
    )


register_builtins()
